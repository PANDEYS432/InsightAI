#  AI Conversation Assistant + Accident Data Agent

An AI-powered web app with two features: chat with your documents using RAG, and analyse India road accident data through a conversational agent.

## Tech Stack

* **Framework:** Flask (Python)
* **AI Models:** Sarvam, GPT-4, Claude, Gemini, Ollama
* **Vector Store:** ChromaDB + Sentence Transformers
* **Data API:** FastAPI + Pandas
* **Document Processing:** PyMuPDF, pdfplumber, BeautifulSoup
* **Deployment:** Render

## Features

* Upload PDFs, URLs, or text and chat with them using any supported LLM
* Generate QA datasets from your documents (JSON / CSV / TXT export)
* Accident Data Agent — ask natural language questions over 13 India road accident datasets (2019–2021) powered by a live REST API

## Getting Started

**Prerequisites:** Python 3.10+, a Sarvam API key ([sarvam.ai](https://sarvam.ai))

**1. Clone the repository**
```bash
git clone https://github.com/your-username/note-ocr-chat.git
cd note-ocr-chat
```

**2. Create a virtual environment and install dependencies**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```

**3. Set up environment variables**
```bash
cp .env.example .env
# Add your SARVAM_API_KEY and other keys in .env
```

**4. Run both servers**
```bash
# Terminal 1 — Data API
python -m uvicorn accident_api.main:app --reload --port 8001

# Terminal 2 — Flask app
python app.py
```

Open `http://localhost:8000` in your browser.


## Contributing

Feel free to open issues or submit pull requests for bug fixes and new features.

