# shipsim API Dokumani

Bu dokuman `shipsim` servisinin REST ve WebSocket arayuzlerini anlatir.

Varsayilan base URL:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Veri Modeli Ozeti

`GET /fleet/current` ve `WS /ws/fleet` cevaplari ayni genel formati kullanir:

```json
{
  "timestamp": "2026-03-30T09:38:45.262246Z",
  "tick": 1301,
  "items": [
    {
      "scenario": "eurasia-corridor",
      "timestamp": "2026-03-30T09:38:45.254578Z",
      "tick": 1301,
      "ship": {},
      "navigation": {},
      "operations": {},
      "machinery": {},
      "power": {},
      "hull": {},
      "cargo": {},
      "environment": {},
      "sensors": {},
      "meta": {},
      "route": {},
      "alerts": [],
      "faults": [],
      "scenario_events": [],
      "alarm_history": []
    }
  ],
  "summary": {}
}
```

## REST Endpointleri

### `GET /health`

Servis ayakta mi kontrol eder.

Ornek cevap:

```json
{
  "status": "ok"
}
```

### `GET /simulation/status`

Calisan simulasyonun genel durumunu verir.

Ornek cevap:

```json
{
  "running": true,
  "active_routes": 4,
  "tick_rate_hz": 2.0,
  "time_scale": 81000.0,
  "latest_tick": 1301,
  "last_timestamp": "2026-03-30T09:38:45.262246+00:00",
  "total_alerts": 13,
  "active_faults": 3,
  "active_events": 0
}
```

Alanlar:

- `running`: simulasyon thread'i aktif mi
- `active_routes`: aktif hat sayisi
- `tick_rate_hz`: gercek zaman tick hizi
- `time_scale`: simule edilen zaman carpani
- `latest_tick`: son snapshot tick numarasi
- `total_alerts`: toplam aktif alarm sayisi
- `active_faults`: aktif fault sayisi
- `active_events`: aktif senaryo event sayisi

### `GET /fleet/routes`

Aktif rota kimliklerini ve temel meta bilgisini verir.

Ornek cevap:

```json
{
  "items": [
    {
      "id": "eurasia-corridor",
      "name": "Istanbul - Lagos",
      "ship_name": "Marmara Atlas",
      "origin_port": "Istanbul",
      "origin_country": "Turkiye",
      "destination_port": "Lagos Harbor",
      "destination_country": "Nigeria",
      "color": "#2470a0"
    }
  ]
}
```

### `GET /fleet/current`

Tum filonun son telemetry snapshot'ini verir.

Kullanim:

```bash
curl http://127.0.0.1:8000/fleet/current
```

Bu endpoint dashboard ve mobil istemciler icin ana veri kaynagidir.

### `GET /fleet/current/{route_id}`

Tek bir gemi/rota icin en son snapshot'i verir.

Ornek:

```bash
curl http://127.0.0.1:8000/fleet/current/eurasia-corridor
```

Ornek cevap alanlari:

```json
{
  "scenario": "eurasia-corridor",
  "ship": {
    "name": "Marmara Atlas",
    "latitude": 36.510604,
    "longitude": 20.240039,
    "speed_knots": 15.97,
    "speed_over_ground_knots": 15.51,
    "heading_deg": 139.6,
    "course_over_ground_deg": 141.63,
    "fuel_percent": 0.0,
    "engine_rpm": 2055.0,
    "route_direction": "return",
    "operation_mode": "underway",
    "ship_role": "container"
  },
  "navigation": {
    "next_waypoint_name": "Aegean Exit",
    "remaining_distance_nm": 504.99,
    "route_deviation_nm": 0.0
  },
  "machinery": {
    "engine_load_percent": 86.8,
    "shaft_power_kw": 8165.0,
    "fuel_flow_lph": 172.3
  },
  "hull": {
    "draft_forward_m": 10.82,
    "draft_aft_m": 11.61,
    "trim_m": 0.79
  },
  "sensors": {
    "gps": {
      "name": "gps",
      "value": "36.51060, 20.24004",
      "unit": null,
      "status": "OK"
    }
  },
  "alerts": []
}
```

### `GET /fleet/history`

Gecmis fleet snapshot listesini verir.

Query parametresi:

- `limit`: donulecek snapshot sayisi

Ornek:

```bash
curl "http://127.0.0.1:8000/fleet/history?limit=5"
```

### `GET /fleet/incidents`

Fault, scenario event ve alarm history bloklarini toplu verir.

Ornek cevap yapisi:

```json
{
  "faults": [
    {
      "route_id": "eurasia-corridor",
      "ship": "Marmara Atlas",
      "items": []
    }
  ],
  "events": [],
  "alarm_history": []
}
```

### `GET /telemetry/current`

`GET /fleet/current` ile ayni veriyi alternatif isimle verir.

Amac:

- eski istemcilerle uyumluluk
- daha genel telemetry endpoint ismi isteyen client'lar

## WebSocket Endpointleri

### `WS /ws/fleet`

Tum fleet snapshot'larini canli olarak gonderir.

Ilk baglantida en son snapshot bir kere yollanir, sonra her tick'te yeni snapshot gelir.

Ornek JavaScript:

```js
const socket = new WebSocket("ws://127.0.0.1:8000/ws/fleet");

socket.onmessage = (event) => {
  const payload = JSON.parse(event.data);
  console.log(payload.tick, payload.items.length);
};
```

### `WS /ws/telemetry`

`/ws/fleet` ile ayni akisi verir.

## Telemetry Alanlari

Her rota icin gelen ana bloklar:

- `ship`: en ust gemi ozeti
- `navigation`: hiz, heading, course, ETA, waypoint
- `operations`: ship role, class, operation mode
- `machinery`: engine load, shaft power, oil pressure, turbo, fuel flow
- `power`: generator, hotel load, battery, shore power
- `hull`: draft, trim, roll, pitch, heel, ballast
- `cargo`: cargo utilization, reefer, tank seviyeleri
- `environment`: dalga, ruzgar, current, gorus, sicaklik
- `sensors`: tekil sensor stack
- `route`: waypoint listesi, port listesi, aktif waypoint, remaining distance
- `alerts`: aktif alarmlar
- `faults`: aktif ve gecmis ariza kayitlari
- `scenario_events`: aktif ve gecmis senaryo eventleri
- `alarm_history`: alarm baslangic/bitis kayitlari

## Sensor Stack

`sensors` objesi asagidaki tipte key-value map olarak doner:

```json
{
  "main_bearing_temp": {
    "name": "main_bearing_temp",
    "value": 84.2,
    "unit": "C",
    "status": "OK"
  }
}
```

Sensor status degerleri:

- `OK`
- `WARN`
- `OFFLINE`

## Hata Kodlari

Yaygin durumlar:

- `404 Fleet telemetry is not ready yet.` -> simulasyon henuz ilk snapshot'i uretmedi
- `404 Route not found.` -> gecersiz `route_id`

## Onerilen Tuketim Sekli

Mobil ya da web istemcisi icin onerilen akis:

1. Acilista `GET /fleet/current`
2. Sonraki canli akis icin `WS /ws/fleet`
3. Listelemek icin `GET /fleet/routes`
4. Tek gemi detay ekrani icin `GET /fleet/current/{route_id}`
5. Olay/inceleme ekranlari icin `GET /fleet/incidents`

## Ornek route_id Degerleri

- `eurasia-corridor`
- `atlantic-bridge`
- `southern-arc`
- `arabian-link`
