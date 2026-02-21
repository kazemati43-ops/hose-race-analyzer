import os
import time
import urllib.robotparser
from urllib.parse import urlparse
import json
import random
import requests
from datetime import datetime

STATE_FILE = "data/processed/crawler_state.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
]

class NetkeibaCrawler:
    """
    netkeiba.com から対象データを安全に取得・キャッシュするためのクローラー基盤。
    ※ 取得したHTMLファイルそのものをローカルに保存し、再取得を防止します。
    ※ 1リクエストごとに確実なスリープを挟み、サーバー負荷を軽減します。
    """

    def __init__(self, cache_dir: str = "data/raw/netkeiba"):
        self.cache_dir = cache_dir
        self.base_url = "https://db.netkeiba.com"
        
        # キャッシュディレクトリの作成
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # クローラーの身元明示（初期化用、実際はリクエスト時にランダム設定）
        self.headers = {
            "User-Agent": random.choice(USER_AGENTS)
        }
        
    def _get_cache_path(self, url: str) -> str:
        """URLから一意なキャッシュファイルパスを生成する"""
        parsed = urlparse(url)
        # クエリパラメータやパスをアンダースコアに置換してファイル名にする
        safe_name = parsed.path.strip("/").replace("/", "_")
        if parsed.query:
            safe_name += "_" + parsed.query.replace("=", "").replace("&", "_")
        safe_name += ".html"
        return os.path.join(self.cache_dir, safe_name)

    def fetch_html(self, url: str, force_refresh: bool = False) -> str:
        """
        URLからHTMLを取得する。
        キャッシュが存在する場合はキャッシュを返し、存在しない場合はHTTPリクエストを発行する。
        """
        cache_path = self._get_cache_path(url)
        
        if not force_refresh and os.path.exists(cache_path):
            print(f"[CACHE HIT] {url}")
            with open(cache_path, "r", encoding="euc-jp", errors="replace") as f:
                return f.read()
                
        # サーバーへのリクエスト（安全装置付き）
        return self._safe_request(url, cache_path)

    def _safe_request(self, url: str, cache_path: str, max_retries: int = 3) -> str:
        """
        指数的バックオフと強制スリープを備えたリクエスト送信
        """
        for attempt in range(max_retries):
            try:
                print(f"[FETCH] Requesting {url} (Attempt {attempt+1}/{max_retries})")
                
                # [安全装置0]: 100リクエスト / 30分 の強制制限
                self._check_global_rate_limit()
                
                # [安全装置1]: リクエスト前の完全ランダムスリープ（5〜15秒）
                pre_sleep = random.uniform(5.0, 15.0)
                print(f"-> Sleeping for {pre_sleep:.1f}s before request...")
                time.sleep(pre_sleep)
                
                # UA動的ローテーション
                headers = {"User-Agent": random.choice(USER_AGENTS)}
                
                response = requests.get(url, headers=headers, timeout=15)
                
                # エラーチェック
                response.raise_for_status()
                
                # NetkeibaはEUC-JPが標準
                response.encoding = 'euc-jp'
                html_content = response.text
                
                # [安全装置2]: 二重取得防除のためのHTMLキャッシュ保存
                with open(cache_path, "w", encoding="euc-jp", errors="replace") as f:
                    f.write(html_content)
                    
                # [安全装置3]: 人間らしい「ページ滞在・読み込み時間」の模倣
                post_sleep = random.uniform(2.0, 5.0)
                print(f"-> Reading page... sleeping for {post_sleep:.1f}s")
                time.sleep(post_sleep)
                    
                return html_content
                
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else None
                print(f"[HTTP ERROR] Status: {status_code}, URL: {url}")
                
                # [死んだふりロジック]: 403 / 429 はアクセス過多。即座に3時間〜24時間のランダム待機を行う
                if status_code in (403, 429):
                    dead_sleep = random.uniform(3 * 3600, 24 * 3600)
                    print(f"!!! CRITICAL STATUS {status_code} DETECTED !!!")
                    print(f"-> Playing dead. Sleeping for {dead_sleep/3600:.2f} hours...")
                    time.sleep(dead_sleep)
                    return ""
                
                # 404は見つからないのでリトライしない
                if status_code == 404:
                    print(f"-> Not Found. Skip retrying.")
                    return ""
                    
            except requests.exceptions.RequestException as e:
                print(f"[REQUEST ERROR] {e}")
                
            # 通常のエラーバックオフ(5 -> 10 -> 20)
            wait_time = 5 * (2 ** attempt)
            print(f"-> Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            
        print(f"[FAILURE] Max retries reached for {url}")
        return ""

    def _check_global_rate_limit(self):
        """100リクエストごとに30分待機するグローバル制限"""
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        state = {"count": 0, "reset_time": 0.0}
        
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)
            except Exception:
                pass
                
        now = time.time()
        
        # ウィンドウ（30分）が過ぎていればリセット
        if now > state["reset_time"]:
            state["count"] = 0
            state["reset_time"] = now + 1800  # 30分後
            
        # 100回に達していたら、ウィンドウが明けるまで待機
        if state["count"] >= 100:
            sleep_time = state["reset_time"] - now
            if sleep_time > 0:
                print(f"[RATE LIMIT] 100 requests reached. Sleeping for {int(sleep_time)} seconds (30 mins strict rule)...")
                time.sleep(sleep_time)
            # 待機明けにリセット
            state["count"] = 0
            state["reset_time"] = time.time() + 1800
            
        # カウントをインクリメントして保存
        state["count"] += 1
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)

if __name__ == "__main__":
    # 使用例:
    crawler = NetkeibaCrawler()
    # テスト対象URL (例: 特定の馬のページ)
    # test_url = "https://db.netkeiba.com/horse/xxxx"
    # html = crawler.fetch_html(test_url)
    print("NetkeibaCrawler loaded.")
