# Руководство по настройке справочной информации (help_info.txt)

## Описание
Файл `document/help_info.txt` содержит часто задаваемые вопросы и ответы для пользователей. Используется для отображения справочной информации в интерфейсе приложения.

## Назначение
- Предоставляет быстрые ответы на частые вопросы пользователей
- Снижает нагрузку на службу поддержки
- Улучшает пользовательский опыт
- Обеспечивает единообразие в ответах

## Формат файла

### Структура блока Q&A
```
Вопрос?
Ответ на вопрос.

Следующий вопрос?
Ответ на следующий вопрос.

И так далее...
```

### Правила форматирования
1. **Каждый блок состоит из вопроса и ответа:**
   - Вопрос (первая строка)
   - Ответ (вторая строка)

2. **Разделители:**
   - Вопрос и ответ разделяются одной пустой строкой
   - Между блоками должны быть две пустые строки

3. **Конец файла:**
   - Файл должен заканчиваться одной пустой строкой

## Правила заполнения

### Вопросы
- Краткие и понятные формулировки
- На английском языке
- Отражают реальные проблемы пользователей
- Используют вопросительные слова (How, What, Can, Do, etc.)
- Примеры: "How does the AI assistant work?", "Can I cancel my subscription?"

### Ответы
- Информативные, но не слишком длинные
- На английском языке
- Дают конкретную информацию
- Используют простой и понятный язык
- Примеры: "The AI uses advanced speech recognition...", "Yes, you can cancel your subscription..."

## Пример корректного формата

```
How does the AI assistant work?
The AI uses advanced speech recognition and natural language technologies to understand your speech and generate natural responses based on the conversation context.

Which languages are supported?
English, Spanish, French, German, Italian, and other popular languages are supported. The complete list is available in the app settings.

What's the difference between modes?
Real-time mode is a live dialogue like a phone call. Voice messages allow you to think through your response and speak at your own pace.

Can I cancel my subscription?
Yes, you can cancel your subscription at any time in your account settings. Access to features is maintained until the end of the paid period.

Are my conversations saved?
Conversations are saved for progress analysis, but you can delete them at any time. We do not share data with third parties.

Do I need special equipment?
Any device with a microphone and internet connection is sufficient. For better quality, we recommend headphones or a headset.

Voice assistant settings?
You can choose one of the available voices, assistant response length and select a topic for conversation. All these settings are available only after authorization.

What problems can arise in the work of an AI assistant?
The AI assistant can make mistakes and is always in training mode. Therefore, if you encounter any problems (incorrect response, lack of response, delays, language change during the conversation, etc.), please repeat your question to the AI assistant.

How do I make sure that the phone screen does not turn off when speaking?
This service cannot affect your device settings and cannot disable the automatic screen lock of your device. To disable the automatic screen lock on your device, you need to do this in the settings of your device (phone, tablet).
```

## Логика работы системы

### Загрузка файла
1. Система читает файл `help_info.txt`
2. Парсит содержимое по блокам (разделитель - две пустые строки)
3. Каждый блок разделяет на вопрос и ответ

### Обработка блоков
```python
# Псевдокод обработки
blocks = content.strip().split("\n\n")
for block in blocks:
    lines = block.strip().split("\n", 1)
    if len(lines) == 2:
        question = lines[0].strip()
        answer = lines[1].strip()
    elif len(lines) == 1:
        # Только вопрос, ответ пустой
        question = lines[0].strip()
        answer = ""
```

### Структура в коде
Каждый блок Q&A получает структуру:
```json
{
  "question": "How does the AI assistant work?",
  "answer": "The AI uses advanced speech recognition and natural language technologies to understand your speech and generate natural responses based on the conversation context."
}
```

## Рекомендации по содержанию

### Категории вопросов
1. **Функциональность** - как работает система
2. **Языки** - поддерживаемые языки
3. **Режимы** - различия между режимами
4. **Подписки** - управление подписками
5. **Данные** - сохранение и конфиденциальность
6. **Оборудование** - технические требования
7. **Настройки** - конфигурация системы
8. **Проблемы** - решение типичных проблем
9. **Технические** - технические вопросы

### Принципы написания
- **Краткость** - вопросы и ответы должны быть краткими
- **Ясность** - понятный язык без жаргона
- **Полнота** - ответы должны быть информативными
- **Актуальность** - информация должна быть актуальной
- **Практичность** - реальные проблемы пользователей

## Обработка ошибок

### Если файл не найден
- Система возвращает пустой список Q&A
- Пользователи не видят справочную информацию

### Если формат некорректный
- Система пытается обработать доступные блоки
- Игнорирует некорректно отформатированные блоки
- Возвращает частичный список Q&A

### Если блоки неполные
- Блоки только с вопросами получают пустые ответы
- Блоки только с ответами игнорируются

## Обновление информации

### Процедура обновления
1. Отредактируйте файл `help_info.txt`
2. Сохраните изменения
3. Изменения применяются немедленно без перезапуска сервера

### Проверка корректности
1. Убедитесь, что формат соответствует требованиям
2. Проверьте, что все тексты на английском языке
3. Убедитесь в корректности разделителей
4. Проверьте пробелы и форматирование

## Примеры вопросов и ответов

### Хорошие примеры
```
How does the AI assistant work?
The AI uses advanced speech recognition and natural language technologies to understand your speech and generate natural responses based on the conversation context.

Can I cancel my subscription?
Yes, you can cancel your subscription at any time in your account settings. Access to features is maintained until the end of the paid period.
```

### Плохие примеры
```
// Слишком длинный вопрос
How does the AI assistant work and what technologies does it use to understand speech and generate responses?
// Слишком короткий ответ
Yes.
// Отсутствие разделителей
How does the AI assistant work?
The AI uses advanced speech recognition and natural language technologies to understand your speech and generate natural responses based on the conversation context.
Can I cancel my subscription?
Yes, you can cancel your subscription at any time in your account settings.
```

## Частые ошибки

### Форматирование
- Отсутствие пустых строк между блоками
- Неправильное количество пустых строк
- Лишние пробелы в начале или конце строк

### Содержание
- Тексты не на английском языке
- Слишком длинные вопросы или ответы
- Отсутствие знаков вопроса в вопросах
- Использование специальных символов

### Структура
- Блоки только с вопросами без ответов
- Блоки только с ответами без вопросов
- Смешивание разных языков в одном блоке

## Важные замечания

1. **Все тексты должны быть на английском языке** - система не поддерживает автоматический перевод
2. **Строго следуйте формату** - неправильное форматирование может привести к ошибкам
3. **Проверяйте пробелы** - лишние пробелы могут нарушить парсинг
4. **Используйте простой язык** - информация должна быть понятна пользователям любого уровня
5. **Избегайте специальных символов** - используйте только стандартные символы ASCII
6. **Проверяйте актуальность** - регулярно обновляйте информацию
7. **Тестируйте изменения** - проверяйте корректность после обновления
