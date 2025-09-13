from prod_config import WS_ENDPOINT

index_page = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VAD + Realtime GPT</title>
    <style>
        body {{
            font-family: 'Arial', sans-serif;
            background-color: #f4f4f4;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }}
        .container {{
            background: #fff;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            border-radius: 8px;
            padding: 20px 40px;
            text-align: center;
            max-width: 600px;
            width: 100%;
        }}
        h1 {{
            font-size: 24px;
            color: #333;
            margin-bottom: 20px;
        }}
        textarea {{
            width: 100%;
            height: 100px;
            margin-bottom: 20px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            resize: vertical;
        }}
        button {{
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 15px 32px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin-top: 20px;
            cursor: pointer;
            border-radius: 4px;
            transition: background-color 0.3s ease;
        }}
        button:hover {{
            background-color: #45a049;
        }}
        button:active {{
            background-color: #3e8e41;
        }}
        .status {{
            margin-top: 15px;
            font-size: 14px;
            color: #666;
            text-align: left;
            max-height: 200px;
            overflow-y: auto;
            border: 1px solid #ddd;
            padding: 10px;
            border-radius: 4px;
        }}

        /* Стили для радио-кнопок */
        .options-container {{
            margin-bottom: 20px;
            text-align: left;
        }}
        .options-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }}
        .radio-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 20px;
        }}
        .radio-option {{
            position: relative;
        }}
        .radio-option input[type="radio"] {{
            position: absolute;
            opacity: 0;
            width: 0;
            height: 0;
        }}
        .radio-option label {{
            display: inline-block;
            padding: 8px 16px;
            background-color: #f0f0f0;
            border: 2px solid #ddd;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
        }}
        .radio-option input[type="radio"]:checked + label {{
            background-color: #4CAF50;
            color: white;
            border-color: #4CAF50;
        }}
        .radio-option input[type="radio"]:focus + label {{
            box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.3);
        }}
        .radio-option label:hover {{
            background-color: #e0e0e0;
        }}
        .radio-option input[type="radio"]:checked + label:hover {{
            background-color: #45a049;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>VAD + Realtime GPT</h1>

        <div class="options-container">
            <div class="options-title">Выберите голос:</div>
            <div class="radio-group" id="voice-options">
                <div class="radio-option">
                    <input type="radio" id="voice-alloy" name="voice" value="alloy" checked>
                    <label for="voice-alloy">Alloy</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="voice-ash" name="voice" value="ash">
                    <label for="voice-ash">Ash</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="voice-coral" name="voice" value="coral">
                    <label for="voice-coral">Coral</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="voice-echo" name="voice" value="echo">
                    <label for="voice-echo">Echo</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="voice-sage" name="voice" value="sage">
                    <label for="voice-sage">Sage</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="voice-shimmer" name="voice" value="shimmer">
                    <label for="voice-shimmer">Shimmer</label>
                </div>
            </div>

            <div class="options-title">Выберите тему:</div>
            <div class="radio-group" id="topic-options">
                <div class="radio-option">
                    <input type="radio" id="topic-none" name="topic" value="none" checked>
                    <label for="topic-none">Без темы</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="topic-intro" name="topic" value="Знакомство, общение с незнакомыми людьми.">
                    <label for="topic-intro">Знакомство</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="topic-hobbies" name="topic" value="Увлечения и хобби. Любимые занятия, любимое времяпрепровождение.">
                    <label for="topic-hobbies">Увлечения и хобби</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="topic-culture" name="topic" value="Культурные различия, культурный обмен.">
                    <label for="topic-culture">Культурные различия</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="topic-news" name="topic" value="Актуальные новости и события.">
                    <label for="topic-news">Актуальные новости и события</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="topic-hypothetical" name="topic" value="Гипотетические ситуации. Что если бы?">
                    <label for="topic-hypothetical">Гипотетические ситуации</label>
                </div>
                <div class="radio-option">
                    <input type="radio" id="topic-future" name="topic" value="Планы на будущее. Мечты, планы и прочее.">
                    <label for="topic-future">Планы на будущее</label>
                </div>
            </div>
        </div>

        <button id="startButton">Начать</button>
        <div class="status" id="status"></div>
    </div>
    <script>
        const wsUrl = '{WS_ENDPOINT}';
        let startButton = document.getElementById('startButton');
        let status = document.getElementById('status');
        let audioContext;
        let ws;
        let isRecording = false;

        let audioQueue = [];
        let isPlaying = false;
        let currentSource = null;

        function initAudioContext() {{
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }}

        function getSelectedVoice() {{
            const voiceRadios = document.getElementsByName('voice');
            for (const radio of voiceRadios) {{
                if (radio.checked) {{
                    return radio.value;
                }}
            }}
            return 'alloy'; // Default voice
        }}

        function getSelectedTopic() {{
            const topicRadios = document.getElementsByName('topic');
            for (const radio of topicRadios) {{
                if (radio.checked) {{
                    return radio.value;
                }}
            }}
            return 'none'; // Default topic
        }}

        function startWebSocket() {{
            const selectedVoice = getSelectedVoice();
            const selectedTopic = getSelectedTopic();

            // Add voice and topic information to the WebSocket URL as query parameters
            const wsUrlWithParams = `${{wsUrl}}?voice=${{selectedVoice}}&topic=${{selectedTopic}}`;

            ws = new WebSocket(wsUrlWithParams);
            ws.binaryType = 'arraybuffer';

            ws.onopen = function() {{
                console.log("WebSocket connection opened");
                addStatusMessage(`Соединение установлено. Голос: ${{selectedVoice}}, Тема: ${{selectedTopic}}`);
                startAudioStreaming();
            }};

            ws.onerror = function(error) {{
                console.error("WebSocket error observed:", error);
                addStatusMessage("Ошибка соединения");
            }};

            ws.onclose = function(event) {{
                console.log("WebSocket connection closed:", event);
                addStatusMessage("Соединение закрыто");
                stopAudioStreaming();
            }};

            ws.onmessage = function(event) {{
                if (typeof event.data === 'string') {{
                    console.log("Message from server:", event.data);
                    addStatusMessage(event.data);
                    if (event.data === "Voice detected. Clearing playback queue.") {{
                        clearPlaybackQueue();
                    }}
                }} else if (event.data instanceof ArrayBuffer) {{
                    audioQueue.push(event.data);
                    if (!isPlaying) {{
                        playNextInQueue();
                    }}
                }}
            }};
        }}

        function addStatusMessage(message) {{
            status.innerHTML += message + "<br>";
            status.scrollTop = status.scrollHeight;
        }}

        function startAudioStreaming() {{
            navigator.mediaDevices.getUserMedia({{
                    audio: {{
                        sampleRate: 16000,
                        channelCount: 1,
                    }}
                }})
                .then(stream => {{
                    const source = audioContext.createMediaStreamSource(stream);
                    const processor = audioContext.createScriptProcessor(16384, 1, 1);

                    processor.onaudioprocess = event => {{
                        const inputBuffer = event.inputBuffer.getChannelData(0);
                        const audioData = convertFloat32ToInt16(inputBuffer);

                        if (ws && ws.readyState === WebSocket.OPEN) {{
                            ws.send(audioData);
                        }}
                    }};

                    source.connect(processor);
                    processor.connect(audioContext.destination);

                    isRecording = true;
                }})
                .catch(error => {{
                    console.error('Error accessing the microphone:', error);
                    addStatusMessage("Ошибка доступа к микрофону");
                }});
        }}

        function stopAudioStreaming() {{
            if (isRecording) {{
                audioContext.close().then(() => {{
                    isRecording = false;
                    addStatusMessage("Запись остановлена");
                }});
            }}
        }}

        function convertFloat32ToInt16(buffer) {{
            let length = buffer.length;
            let buf = new Int16Array(length);
            while (length--) {{
                buf[length] = Math.min(1, buffer[length]) * 0x7FFF;
            }}
            return buf.buffer;
        }}

        function playNextInQueue() {{
            if (audioQueue.length === 0) {{
                isPlaying = false;
                return;
            }}

            isPlaying = true;

            if (!audioContext || audioContext.state === 'closed') {{
                initAudioContext();
            }}

            if (audioContext.state === 'suspended') {{
                audioContext.resume();
            }}

            let audioData = audioQueue.shift();
            audioContext.decodeAudioData(audioData, (buffer) => {{
                if (currentSource) {{
                    currentSource.stop();
                }}
                let source = audioContext.createBufferSource();
                source.buffer = buffer;
                source.connect(audioContext.destination);
                source.start(0);
                currentSource = source;
                source.onended = () => {{
                    currentSource = null;
                    playNextInQueue();
                }};
            }}, (err) => {{
                console.error("Ошибка декодирования аудио", err);
                playNextInQueue();
            }});
        }}

        function clearPlaybackQueue() {{
            if (currentSource) {{
                currentSource.stop();  // Останавливаем текущее воспроизведение
                currentSource = null;
            }}
            audioQueue = [];  // Очищаем очередь
            isPlaying = false;
            console.log("Очередь воспроизведения очищена");
        }}

        startButton.addEventListener('click', () => {{
            // Скрываем кнопки выбора и переключаемся в режим разговора
            document.querySelectorAll('.options-container').forEach(container => {{
                container.style.display = 'none';
            }});

            initAudioContext();
            startWebSocket();
            startButton.style.display = 'none';
        }});
    </script>
</body>
</html>

"""