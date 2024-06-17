# Folosește imaginea oficială Python de pe Docker Hub
FROM python:3.9-slim

# Setează directorul de lucru în container
WORKDIR /app

# Copiază fișierul requirements.txt în container
COPY requirements.txt .

# Instalează dependențele specificate în requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copiază restul fișierelor aplicației în container
COPY . .

# Setează variabilele de mediu pentru Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Expune portul 5000 pentru aplicația Flask
EXPOSE 5000

# Comanda pentru a rula aplicația Flask
CMD ["flask", "run"]
