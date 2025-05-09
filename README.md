# Create virtual environment with:
python -m venv connector

# Activate on Mac/Linux:
source connector/bin/activate

# Or on Windows:
# connector\Scripts\activate

# Then install dependencies:
pip install -r server/requirements.txt

# Run with Docker:
docker-compose up --build
