# shipsim

shipsim, dunya capinda hazir hatlari otomatik calistiran bir gemi simulasyonudur.

Tek servis icinde sunlari birlikte verir:

- web arayuzu
- REST API
- WebSocket telemetry yayini
- CLI ozet modu

Proje varsayilan olarak 4 gemilik filoyu otomatik baslatir. Manuel `start/stop` akisi yoktur; servis kalkinca simulasyon da kalkar.

## Icerik

- [Hizli Baslangic](#hizli-baslangic)
- [Docker Ile Calistirma](#docker-ile-calistirma)
- [Lokal Gelistirme](#lokal-gelistirme)
- [CLI Komutlari](#cli-komutlari)
- [API Ozet](#api-ozet)
- [Proje Yapisi](#proje-yapisi)
- [Sorun Giderme](#sorun-giderme)

Detayli API dokumani: [docs/API.md](docs/API.md)

## Hizli Baslangic

En kolay yol Docker'dir.

```bash
docker build -t shipsim-app .
docker run --name shipsim-app -p 8000:8000 shipsim-app
```

Servis ayaga kalkinca:

- Dashboard: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

## Docker Ile Calistirma

### 1. Image build et

```bash
docker build -t shipsim-app .
```

### 2. Container calistir

```bash
docker run -d --name shipsim-app -p 8000:8000 shipsim-app
```

### 3. Log bak

```bash
docker logs -f shipsim-app
```

### 4. Durdur ve sil

```bash
docker stop shipsim-app
docker rm shipsim-app
```

## Lokal Gelistirme

Gereksinimler:

- Python 3.11+
- Node.js 20+
- npm

### Python kurulumu

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### Frontend kurulumu

```bash
cd frontend
npm install
npm run build
```

### Uygulamayi lokal baslat

```bash
shipsim serve --host 0.0.0.0 --port 8000
```

Ardindan:

- Web: `http://127.0.0.1:8000/`
- OpenAPI docs: `http://127.0.0.1:8000/docs`

## Gelistirme Modu

Backend ve frontend ayri ayri calistirilabilir.

### Backend

```bash
shipsim serve --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite gelistirme sunucusu backend API'ye baglanir. Uretim build'i `shipsim/web` altina cikar.

## CLI Komutlari

### API + dashboard servisi

```bash
shipsim serve --host 0.0.0.0 --port 8000
```

### Terminal ozet modu

```bash
shipsim run --catalog scenarios/world_fleet.json
```

### Farkli katalog ile baslatma

```bash
shipsim serve --catalog scenarios/world_fleet.json
```

## API Ozet

REST:

- `GET /health`
- `GET /simulation/status`
- `GET /fleet/routes`
- `GET /fleet/current`
- `GET /fleet/current/{route_id}`
- `GET /fleet/history?limit=10`
- `GET /fleet/incidents`
- `GET /telemetry/current`

WebSocket:

- `WS /ws/fleet`
- `WS /ws/telemetry`

Detay ve ornek cevaplar icin: [docs/API.md](docs/API.md)

## Varsayilan Filo

Varsayilan katalog dosyasi:

- `scenarios/world_fleet.json`

Bu katalog su an otomatik calisan 4 hat icerir:

- `eurasia-corridor` -> Marmara Atlas
- `atlantic-bridge` -> North Sea Relay
- `southern-arc` -> Atlantic Meridian
- `arabian-link` -> Gulf Horizon

## Proje Yapisi

```text
shipsim/
  shipsim/
    api.py
    cli.py
    fleet.py
    models.py
    sensors.py
    web/
  frontend/
    src/
  scenarios/
    world_fleet.json
  Dockerfile
  pyproject.toml
  requirements.txt
  README.md
  docs/
    API.md
```

## Baska Birine Gonderirken

Birine projeyi verdiginde en hizli yol su:

1. Repo klasorunu gondersin ya da clone etsin.
2. Docker kurulu olsun.
3. Asagidaki iki komutu calistirsin:

```bash
docker build -t shipsim-app .
docker run --name shipsim-app -p 8000:8000 shipsim-app
```

Bu kadar. Sonra `http://127.0.0.1:8000/` adresinden sistemi gorebilir.

## Sorun Giderme

### Tarayici eski arayuzu gosteriyor

Statik bundle cache'de kalmis olabilir.

```text
Ctrl + F5
```

### 8000 portu dolu

Farkli port deneyin:

```bash
docker run --name shipsim-app -p 8080:8000 shipsim-app
```

### WebSocket verisi gelmiyor

Sunucunun logunu kontrol edin:

```bash
docker logs -f shipsim-app
```

### API cevap vermiyor

Asagidaki endpoint ile servis durumunu test edin:

```bash
curl http://127.0.0.1:8000/health
```
