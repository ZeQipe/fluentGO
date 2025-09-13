from prod_config import WS_ENDPOINT, UPLOAD_ENDPOINT
 
index_page = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Аудиосообщения + Realtime GPT</title>
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
        .button-container {{
            position: relative;
            margin-top: 20px;
        }}
        .record-button {{
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 15px 32px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            cursor: pointer;
            border-radius: 4px;
            transition: all 0.3s ease;
            width: 200px;
            height: 60px;
            user-select: none;
        }}
        .record-button:hover {{
            background-color: #45a049;
        }}
        .record-button.recording {{
            background-color: #f44336;
            box-shadow: 0 0 10px rgba(244, 67, 54, 0.5);
            transform: scale(1.05);
        }}
        .record-button:active {{
            transform: scale(0.98);
        }}
        .record-button.initializing {{
            background-color: #2196F3;
            cursor: wait;
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
        <h1>Аудиосообщения + Realtime GPT</h1>

        <!-- Добавляем выбор голоса и темы -->
        <div class="options-container" id="options-container">
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

        <div class="button-container">
            <button id="recordButton" class="record-button">Старт</button>
        </div>
        <div class="status" id="status"></div>
    </div>
    <script>
        const apiUrl = '{UPLOAD_ENDPOINT}';
        const wsUrl = '{WS_ENDPOINT}';
        let recordButton = document.getElementById('recordButton');
        let status = document.getElementById('status');
        let optionsContainer = document.getElementById('options-container');
        let audioContext;
        let ws;
        let isRecording = false;

        let audioQueue = [];
        let isPlaying = false;
        let currentSource = null;

        // For recording functionality
        let mediaRecorder;
        let audioChunks = [];
        let stream;

        // Client ID for tracking across endpoints
        let clientId = null;

        // Connection and initialization states
        let isConnected = false;
        let isInitialized = false;
        let hasMicrophonePermission = false;
        let assistantReady = false;

        // Выбор голоса и темы
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

        function initAudioContext() {{
            if (!audioContext) {{
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }}
        }}

        function startWebSocket() {{
            if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {{
                return; // WebSocket already open or connecting
            }}

            // Получаем выбранные голос и тему
            const selectedVoice = getSelectedVoice();
            const selectedTopic = getSelectedTopic();

            // Добавляем параметры голоса и темы в URL WebSocket
            const wsUrlWithParams = `${{wsUrl}}?voice=${{selectedVoice}}&topic=${{selectedTopic}}`;

            ws = new WebSocket(wsUrlWithParams);
            ws.binaryType = 'arraybuffer';

            ws.onopen = function() {{
                console.log("WebSocket connection opened with voice: " + selectedVoice + ", topic: " + selectedTopic);
                addStatusMessage(`WebSocket соединение открыто. Голос: ${{selectedVoice}}, Тема: ${{selectedTopic}}`);
                isConnected = true;
                checkInitializationComplete();
            }};

            ws.onerror = function(error) {{
                console.error("WebSocket error observed:", error);
                addStatusMessage("Ошибка соединения");
                isConnected = false;
                resetButton();
            }};

            ws.onclose = function(event) {{
                console.log("WebSocket connection closed:", event);
                addStatusMessage("Соединение закрыто");
                isConnected = false;

                // Try to reconnect if initialization was previously successful
                if (isInitialized) {{
                    addStatusMessage("Attempting to reconnect...");
                    setTimeout(startWebSocket, 3000);
                }}
            }};

            ws.onmessage = function(event) {{
                if (typeof event.data === 'string') {{
                    console.log("Message from server:", event.data);

                    // Check if this is a client ID message
                    if (event.data.startsWith('CONNECTED:')) {{
                        clientId = event.data.split(':')[1];
                        console.log("Received client ID:", clientId);
                        // Store client ID in localStorage for persistence
                        localStorage.setItem('clientId', clientId);
                        return;
                    }}

                    // Check if this is the assistant initialization message
                    if (event.data === "Настройки применены. Ассистент инициализирован.") {{
                        assistantReady = true;
                        addStatusMessage(event.data);
                        checkInitializationComplete();
                        return;
                    }}

                    addStatusMessage(event.data);
                    if (event.data === "Voice detected. Clearing playback queue.") {{
                        clearPlaybackQueue();
                    }}
                }} else if (event.data instanceof ArrayBuffer) {{
                    if (!isRecording) {{ // Only add to queue if not recording
                        audioQueue.push(event.data);
                        if (!isPlaying) {{
                            playNextInQueue();
                        }}
                    }}
                }}
            }};
        }}

        function requestMicrophoneAccess() {{
            recordButton.textContent = "Запрос микрофона...";
            recordButton.classList.add('initializing');

            navigator.mediaDevices.getUserMedia({{ 
                audio: {{
                    sampleRate: 16000,
                    channelCount: 1
                }} 
            }})
            .then(str => {{
                // Successfully got permission, store the stream
                stream = str;

                // Immediately stop the tracks, we don't need them yet
                stream.getTracks().forEach(track => track.stop());

                hasMicrophonePermission = true;
                addStatusMessage("Доступ к микрофону получен");
                checkInitializationComplete();
            }})
            .catch(error => {{
                console.error('Error accessing the microphone:', error);
                addStatusMessage("Ошибка доступа к микрофону. Пожалуйста, разрешите доступ и попробуйте снова.");
                resetButton();
            }});
        }}

        function checkInitializationComplete() {{
            // Check if all required conditions are met
            if (isConnected && hasMicrophonePermission && assistantReady) {{
                isInitialized = true;
                addStatusMessage("Все готово! Теперь вы можете записывать сообщения.");
                recordButton.textContent = "Удерживайте для записи";
                recordButton.classList.remove('initializing');

                // Скрываем контейнер с опциями
                optionsContainer.style.display = 'none';

                // Enable the hold-to-record functionality
                enableRecordingMode();
            }} else if (isConnected && hasMicrophonePermission && !assistantReady) {{
                // All set but waiting for assistant initialization
                recordButton.textContent = "Ожидание ассистента...";
                recordButton.classList.add('initializing');
                addStatusMessage("Ожидание инициализации ассистента...");
            }}
        }}

        function enableRecordingMode() {{
            // Remove the initialization click handler
            recordButton.removeEventListener('click', initializeApp);

            // Add press-and-hold recording handlers
            recordButton.addEventListener('mousedown', handleRecordStart);
            recordButton.addEventListener('mouseup', handleRecordStop);
            recordButton.addEventListener('mouseleave', handleRecordCancel);

            // Touch support for mobile devices
            recordButton.addEventListener('touchstart', handleTouchStart);
            recordButton.addEventListener('touchend', handleRecordStop);
            recordButton.addEventListener('touchcancel', handleRecordCancel);
        }}

        function handleRecordStart(e) {{
            e.preventDefault(); // Prevent text selection
            startRecording();
        }}

        function handleTouchStart(e) {{
            e.preventDefault(); // Prevent scrolling
            startRecording();
        }}

        function handleRecordStop() {{
            stopRecording();
        }}

        function handleRecordCancel() {{
            if (isRecording) {{
                stopRecording();
            }}
        }}

        function addStatusMessage(message) {{
            status.innerHTML += message + "<br>";
            status.scrollTop = status.scrollHeight;
        }}

        function convertFloat32ToInt16(buffer) {{
            let length = buffer.length;
            let buf = new Int16Array(length);
            while (length--) {{
                buf[length] = Math.min(1, buffer[length]) * 0x7FFF;
            }}
            return buf.buffer;
        }}

        // Замените функцию startRecording() на эту:
        function startRecording() {{
            // If not initialized, don't do anything
            if (!isInitialized) return;
            
            // Clear existing playback first
            clearPlaybackQueue();
            
            isRecording = true;
            recordButton.classList.add('recording');
            recordButton.textContent = "Отпустите для отправки";
            addStatusMessage("Запись началась...");
            
            // Буфер для хранения собранных аудиоданных
            audioChunks = [];
            
            navigator.mediaDevices.getUserMedia({{
                audio: {{
                    sampleRate: 16000,
                    channelCount: 1
                }}
            }})
            .then(str => {{
                stream = str;
                
                const source = audioContext.createMediaStreamSource(stream);
                const processor = audioContext.createScriptProcessor(16384, 1, 1);
                
                // Сохраняем ссылки для последующего отключения
                window.source = source;
                window.processor = processor;

                processor.onaudioprocess = event => {{
                    if (isRecording) {{
                        const inputBuffer = event.inputBuffer.getChannelData(0);
                        const audioData = convertFloat32ToInt16(inputBuffer);
                        
                        // Сохраняем данные в audioChunks
                        audioChunks.push(audioData);
                    }}
                }};

                source.connect(processor);
                processor.connect(audioContext.destination);
            }})
            .catch(error => {{
                console.error('Error accessing the microphone:', error);
                addStatusMessage("Ошибка доступа к микрофону");
                resetRecordingState();
            }});
        }}

        function createWavFile(audioData) {{
            // audioData - массив ArrayBuffer с Int16 сэмплами
            
            // Вычисляем общую длину всех аудио-фрагментов
            let totalLength = 0;
            for (let i = 0; i < audioData.length; i++) {{
                totalLength += audioData[i].byteLength;
            }}
            
            // Создаем новый буфер с местом для заголовка + всех аудиоданных
            const wavDataView = new DataView(new ArrayBuffer(44 + totalLength));
            
            // Записываем WAV-заголовок
            // "RIFF" chunk descriptor
            writeString(wavDataView, 0, 'RIFF');
            wavDataView.setUint32(4, 36 + totalLength, true); // Размер файла - 8
            writeString(wavDataView, 8, 'WAVE');
            
            // "fmt " sub-chunk
            writeString(wavDataView, 12, 'fmt ');
            wavDataView.setUint32(16, 16, true); // Subchunk1Size (16 для PCM)
            wavDataView.setUint16(20, 1, true); // AudioFormat (1 для PCM)
            wavDataView.setUint16(22, 1, true); // NumChannels (1 для моно)
            wavDataView.setUint32(24, 44100, true); // SampleRate (16000 Гц)
            wavDataView.setUint32(28, 44100 * 2, true); // ByteRate (SampleRate * NumChannels * BitsPerSample/8)
            wavDataView.setUint16(32, 2, true); // BlockAlign (NumChannels * BitsPerSample/8)
            wavDataView.setUint16(34, 16, true); // BitsPerSample (16 бит)
            
            // "data" sub-chunk
            writeString(wavDataView, 36, 'data');
            wavDataView.setUint32(40, totalLength, true); // Subchunk2Size
            
            // Копируем аудиоданные в буфер после заголовка
            let offset = 44;
            for (let i = 0; i < audioData.length; i++) {{
                const dataView = new Uint8Array(audioData[i]);
                for (let j = 0; j < dataView.length; j++) {{
                    wavDataView.setUint8(offset, dataView[j]);
                    offset++;
                }}
            }}
            
            return wavDataView.buffer;
        }}

        // Вспомогательная функция для записи строк в DataView
        function writeString(dataView, offset, string) {{
            for (let i = 0; i < string.length; i++) {{
                dataView.setUint8(offset + i, string.charCodeAt(i));
            }}
        }}

        // Теперь измените функцию stopRecording(), заменив создание Blob:
        function stopRecording() {{
            if (!isRecording) return;
            
            isRecording = false;
            recordButton.classList.remove('recording');
            recordButton.textContent = "Удерживайте для записи";
            
            // Останавливаем запись
            if (window.source) {{
                window.source.disconnect();
                window.processor.disconnect();
            }}
            
            addStatusMessage("Запись остановлена");
            
            // Готовим данные для отправки
            if (audioChunks.length === 0) {{
                addStatusMessage("Аудио не записано");
                return;
            }}
            
            // Создаем правильный WAV-файл
            const wavBuffer = createWavFile(audioChunks);
            const wavBlob = new Blob([wavBuffer], {{ type: 'audio/wav' }});
            
            let formData = new FormData();
            formData.append('file', wavBlob, 'audio.wav');
            formData.append('client_id', clientId);

            addStatusMessage('Отправка аудио на сервер...');
            fetch(`${{apiUrl}}/`, {{
                method: 'POST',
                body: formData
            }})
            .then(response => {{
                if (!response.ok) {{
                    throw new Error('Network response was not ok');
                }}
                addStatusMessage("Аудио отправлено, ожидание ответа...");
            }})
            .catch(error => {{
                console.error('There was a problem with the fetch operation:', error);
                addStatusMessage("Ошибка отправки аудио на сервер");
            }});
            
            // Close audio tracks
            if (stream) {{
                stream.getTracks().forEach(track => track.stop());
            }}
        }}
        
        function resetRecordingState() {{
            isRecording = false;
            recordButton.classList.remove('recording');
            recordButton.textContent = "Удерживайте для записи";

            if (stream) {{
                stream.getTracks().forEach(track => track.stop());
            }}
        }}

        function resetButton() {{
            recordButton.textContent = "Старт";
            recordButton.classList.remove('initializing');
            recordButton.classList.remove('recording');
            isInitialized = false;
            assistantReady = false;

            // Показываем контейнер с опциями снова
            optionsContainer.style.display = 'block';
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
                currentSource.stop();  // Stop current playback
                currentSource = null;
            }}
            audioQueue = [];  // Clear queue
            isPlaying = false;
            console.log("Playback queue cleared");
            addStatusMessage("Очередь воспроизведения очищена");
        }}

        function initializeApp() {{
            // If already initializing, don't do anything
            if (recordButton.classList.contains('initializing')) return;

            addStatusMessage("Инициализация...");

            // Initialize audio context first
            initAudioContext();

            // Start connecting to WebSocket
            startWebSocket();

            // Request microphone permission
            requestMicrophoneAccess();
        }}

        // Check if we have a stored client ID from a previous session
        window.onload = function() {{
            const storedClientId = localStorage.getItem('clientId');
            if (storedClientId) {{
                clientId = storedClientId;
                console.log("Retrieved stored client ID:", clientId);
            }}

            // Set up the initial click handler
            recordButton.addEventListener('click', initializeApp);
        }};

        // Handle page visibility changes
        document.addEventListener('visibilitychange', function() {{
            if (document.visibilityState === 'hidden' && isRecording) {{
                stopRecording();
            }}
        }});
    </script>
</body>
</html>
"""