document.addEventListener('DOMContentLoaded', () => {
    const btnAnalyze = document.getElementById('btn-analyze-febS');
    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-textarea');
    const sendBtn = document.getElementById('btn-send');

    // State
    let currentSessionId = null;

    // API Base URL (Relative path since we'll serve it from the same domain locally or via proxy)
    const API_BASE = 'http://localhost:8000/api';

    // Utilities
    const scrollToBottom = () => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    };

    const setInputState = (enabled) => {
        chatInput.disabled = !enabled;
        sendBtn.disabled = !enabled || chatInput.value.trim() === '';
    };

    // Chat Input Event Listner
    chatInput.addEventListener('input', () => {
        if(currentSessionId) {
            sendBtn.disabled = chatInput.value.trim() === '';
        }
    });

    // Message Rendering
    const appendMessage = (content, type = 'system') => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${type}-message`;
        
        const bubble = document.createElement('div');
        bubble.className = `message-bubble ${type}-bubble`;
        
        // Ensure HTML is rendered, not just string (for bolding etc.)
        bubble.innerHTML = content.replace(/\n/g, '<br>');
        
        msgDiv.appendChild(bubble);
        chatMessages.appendChild(msgDiv);
        scrollToBottom();
    };

    const showTypingIndicator = () => {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message ai-message typing-indicator-container';
        msgDiv.id = 'typing-indicator';
        
        msgDiv.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        
        chatMessages.appendChild(msgDiv);
        scrollToBottom();
    };

    const removeTypingIndicator = () => {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    };

    const renderAnalysisResult = (data) => {
        let html = `<div><strong>📊 フェブラリーS 分析完了</strong></div>`;
        html += `<div style="margin-top: 10px;">${data.ai_reasoning}</div>`;
        
        // Render Top 5 Horses
        if (data.horse_results && data.horse_results.length > 0) {
            html += `<div class="result-card">`;
            
            const topHorses = data.horse_results.slice(0, 5);
            topHorses.forEach(horse => {
                html += `
                    <div class="horse-row">
                        <div class="horse-info">
                            <div class="horse-name">
                                <span class="horse-rank">#${horse.predicted_rank}</span>
                                ${horse.name}
                                <span class="horse-score">Score: ${horse.score}</span>
                            </div>
                            <ul class="conditions-list">
                `;
                
                // Top 2 conditions
                const conds = horse.matched_conditions.slice(0, 2);
                conds.forEach(c => {
                    html += `
                        <li class="condition-item">
                            該当: ${c.name}
                            <span class="condition-tag">勝率 ${(c.median_rate * 100).toFixed(0)}%</span>
                            <span class="condition-tag">実績 ${c.n_top3}/${c.n_all}頭</span>
                        </li>
                    `;
                });
                
                html += `       </ul>
                        </div>
                    </div>
                `;
            });
            
            html += `</div>`;
        }
        
        appendMessage(html, 'ai');
    };

    // Actions
    btnAnalyze.addEventListener('click', async () => {
        const raceId = btnAnalyze.getAttribute('data-race-id');
        const raceDate = btnAnalyze.getAttribute('data-race-date');
        
        // UI Updates
        btnAnalyze.disabled = true;
        appendMessage('フェブラリーSの分析を開始します。過去10年分のデータを抽出し、推論エンジンを回しています...', 'user');
        showTypingIndicator();
        
        try {
            const response = await fetch(`${API_BASE}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ race_event_id: raceId, target_date: raceDate })
            });
            
            removeTypingIndicator();
            
            if (!response.ok) {
                const errorData = await response.json();
                appendMessage(`⚠️ エラーが発生しました: ${errorData.detail}`, 'system');
                btnAnalyze.disabled = false;
                return;
            }
            
            const result = await response.json();
            currentSessionId = result.session_id;
            
            renderAnalysisResult(result.data);
            
            // Allow follow up chat
            setInputState(true);
            
        } catch (error) {
            removeTypingIndicator();
            appendMessage('⚠️ サーバーへの接続に失敗しました。APIが起動しているか確認してください。', 'system');
            btnAnalyze.disabled = false;
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const message = chatInput.value.trim();
        if (!message || !currentSessionId) return;
        
        // UI Updates
        appendMessage(message, 'user');
        chatInput.value = '';
        setInputState(false);
        showTypingIndicator();
        
        try {
            const response = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: currentSessionId, message: message })
            });
            
            removeTypingIndicator();
            
            if (!response.ok) {
                appendMessage('⚠️ メッセージの送信に失敗しました。', 'system');
            } else {
                const data = await response.json();
                appendMessage(data.reply, 'ai');
            }
        } catch (error) {
            removeTypingIndicator();
            appendMessage('⚠️ サーバーエラーが発生しました。', 'system');
        } finally {
            setInputState(true);
            chatInput.focus();
        }
    });
});
