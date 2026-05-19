Временное содержание этого файла

# UltraTrace Backend – Quick Start

- Python 3.10 или новее.

2. Установка зависимостей

```bash
python -m venv venv
source venv/bin/activate      # Linux/macOS
# или venv\Scripts\activate   # Windows
pip install -r requirements.txt

3. Подготовка данных

Положите папку с исследованием (содержащую файлы .dicom или .ult, аудио, .TextGrid) в data/sample_study.

По умолчанию сервер ищет данные в data/sample_study.
Чтобы указать другой путь, установите переменную окружения:

bash
export ULTRA_TRACE_DATA=/полный/путь/к/папке
(для Windows: set ULTRA_TRACE_DATA=C:\путь\к\папке)

4. Запуск сервера
bash
uvicorn app.main:app --reload
```
