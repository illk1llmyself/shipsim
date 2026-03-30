# shipsim API Dokumani

Bu dokuman `shipsim` servisinin REST ve WebSocket arayuzlerini, donen veri yapilarini ve istemci tarafinda nasil tuketilmesi gerektigini anlatir.

Varsayilan base URL:

```text
http://127.0.0.1:8000
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## Hangi Endpoint Ne Icin Kullanilir

- `GET /health`
  Servis ayakta mi kontrol et.
- `GET /simulation/status`
  Simulasyon su an calisiyor mu, kac rota var, zaman carpani ne.
- `GET /fleet/routes`
  Rota listesi ve temel gemi meta bilgisi.
- `GET /fleet/current`
  Tum filonun son anlik snapshot'i.
- `GET /fleet/current/{route_id}`
  Tek bir geminin son anlik telemetry paketi.
- `GET /fleet/history`
  Son N snapshot gecmisi.
- `GET /fleet/incidents`
  Fault, scenario event ve alarm history bloklari.
- `GET /telemetry/current`
  `GET /fleet/current` ile ayni veri, alternatif isim.
- `WS /ws/fleet`
  Canli fleet stream.
- `WS /ws/telemetry`
  `WS /ws/fleet` ile ayni stream.

## Ana Veri Yapisi

`GET /fleet/current` ve `WS /ws/fleet` cevaplari ayni uzeri yapida veri dondurur:

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

Ust seviye alanlar:

- `timestamp`
  Fleet snapshot'in uretildigi zaman.
- `tick`
  Fleet tick numarasi.
- `items`
  Her rota/gemi icin bir telemetry nesnesi.
- `summary`
  Dashboard ozetleri. Ornek: aktif rota sayisi, toplam alarm sayisi, aktif fault sayisi.

## REST Endpointleri

### `GET /health`

Amac:

- servis ayakta mi kontrol etmek
- container healthcheck icin kullanmak

Ornek cevap:

```json
{
  "status": "ok"
}
```

### `GET /simulation/status`

Amac:

- simulasyon thread'i calisiyor mu
- kac rota aktif
- tick hizi ve zaman carpani ne

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

- `running`
  Simulasyon ayakta mi.
- `active_routes`
  O anda yayinlanan rota sayisi.
- `tick_rate_hz`
  Gercek zamanda saniyede kac kez snapshot uretildigi.
- `time_scale`
  Simulasyon zaman carpani.
- `latest_tick`
  Son uretilen tick.
- `last_timestamp`
  Son snapshot zamani.
- `total_alerts`
  Tum filodaki aktif alarm sayisi.
- `active_faults`
  Aktif fault kaydi sayisi.
- `active_events`
  Aktif senaryo event sayisi.

### `GET /fleet/routes`

Amac:

- rota listesi cekmek
- harita legend'i, filtre listesi veya dropdown doldurmak

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

Route meta alanlari:

- `id`
  API'de route secmek icin kullanilan kimlik.
- `name`
  Hat adi.
- `ship_name`
  O hatta calisan gemi adi.
- `origin_port`, `origin_country`
  Kalkis bilgisi.
- `destination_port`, `destination_country`
  Varis bilgisi.
- `color`
  Harita/arayuz rengi.

### `GET /fleet/current`

Amac:

- tum filonun son durumunu tek istekte almak
- dashboard ilk yuklenisinde temel veri cekmek
- mobil veya web client'ta ilk snapshot'i almak

Kullanim:

```bash
curl http://127.0.0.1:8000/fleet/current
```

Donen veri:

- ustte `timestamp`, `tick`, `items`, `summary`
- `items` dizisinde her gemi icin detayli telemetry nesnesi

### `GET /fleet/current/{route_id}`

Amac:

- tek gemi detay sayfasi
- mobil detay ekranlari
- route bazli monitoring

Ornek:

```bash
curl http://127.0.0.1:8000/fleet/current/eurasia-corridor
```

Ornek cevap:

```json
{
  "scenario": "eurasia-corridor",
  "timestamp": "2026-03-30T09:38:45.254578Z",
  "tick": 1301,
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
    "speed_over_ground_knots": 15.51,
    "speed_through_water_knots": 15.97,
    "course_over_ground_deg": 141.63,
    "heading_deg": 139.6,
    "desired_heading_deg": 61.16,
    "drift_angle_deg": 2.04,
    "rate_of_turn_deg_min": 6.24,
    "rudder_angle_deg": -9.1,
    "turn_radius_nm": 2.374,
    "eta_hours": 32.56,
    "remaining_distance_nm": 504.99,
    "next_waypoint_name": "Aegean Exit",
    "distance_to_next_nm": 252.77,
    "route_deviation_nm": 0.0,
    "gps_satellites": 11.0,
    "gps_hdop": 0.98,
    "route_direction": "return",
    "nav_status": "UNDERWAY"
  }
}
```

Bu endpointin dondugu ana bloklar altta tek tek aciklanmistir.

### `GET /fleet/history`

Amac:

- son N snapshot'i almak
- replay benzeri basit gecmis ekranlari yapmak
- trend veya gecmis kiyaslama yapmak

Query parametresi:

- `limit`
  kac snapshot donsun

Ornek:

```bash
curl "http://127.0.0.1:8000/fleet/history?limit=5"
```

Cevap tipi:

```json
[
  {
    "timestamp": "...",
    "tick": 1297,
    "items": [],
    "summary": {}
  }
]
```

### `GET /fleet/incidents`

Amac:

- aktif ve gecmis incident bloklarini tek istekte toplamak
- operasyon merkezi, alarm paneli, ariza inceleme ekranlari

Ornek cevap:

```json
{
  "faults": [
    {
      "route_id": "eurasia-corridor",
      "ship": "Marmara Atlas",
      "items": [
        {
          "code": "low_oil_pressure",
          "title": "Low oil pressure",
          "severity": "critical",
          "status": "resolved",
          "message": "Yaglama basinci duzensiz.",
          "started_at": "2026-03-30T09:38:19.789855Z",
          "expected_end_at": null,
          "ended_at": "2026-03-30T09:38:28.595674Z",
          "effects": {
            "oil_pressure_delta_bar": -1.4,
            "fuel_flow_penalty": 0.06
          }
        }
      ]
    }
  ],
  "events": [],
  "alarm_history": []
}
```

Bloklar:

- `faults`
  Rota bazli ariza listesi.
- `events`
  Rota bazli senaryo event listesi.
- `alarm_history`
  Rota bazli alarm gecmisi.

### `GET /telemetry/current`

`GET /fleet/current` ile ayni veriyi dondurur.

Kullanma nedeni:

- eski istemci uyumlulugu
- telemetry odakli daha genel endpoint ismi

## WebSocket Endpointleri

### `WS /ws/fleet`

Amac:

- canli telemetry akisi almak
- polling yerine stream kullanmak

Davranis:

1. baglaninca en son snapshot bir kere gonderilir
2. sonra her tick'te yeni snapshot gelir

Ornek JavaScript:

```js
const socket = new WebSocket("ws://127.0.0.1:8000/ws/fleet");

socket.onmessage = (event) => {
  const payload = JSON.parse(event.data);
  console.log(payload.tick, payload.items.length);
};
```

WebSocket mesaj yapisi:

- `GET /fleet/current` ile aynidir

### `WS /ws/telemetry`

`WS /ws/fleet` ile ayni akisi verir.

## Tek Gemi Snapshot Anatomisi

`GET /fleet/current/{route_id}` icindeki ana bloklar:

- `scenario`
  Senaryo veya rota kimligi.
- `timestamp`
  Bu gemi snapshot'inin zamani.
- `tick`
  Snapshot tick numarasi.
- `ship`
  Harita ustunde gosterilecek hizli ozet.
- `navigation`
  Kurs, hiz, ETA, waypoint bilgileri.
- `operations`
  Operasyon modu ve gemi profili bilgileri.
- `machinery`
  Ana makine ve sevk sistemi hesaplanmis degerleri.
- `power`
  Jenerator ve elektrik sistemi ozeti.
- `hull`
  Draft, trim, heel, roll gibi govde/stabilite verileri.
- `cargo`
  Yuk ve servis tanklari.
- `environment`
  Dis ortam verileri.
- `sensors`
  Tek tek sensor okumalarinin map yapisi.
- `meta`
  Route ve gemi kimlik bilgileri.
- `route`
  Waypoint ve port listesi.
- `alerts`
  O an aktif alarm listesi.
- `faults`
  Aktif veya gecmis fault listesi.
- `scenario_events`
  Aktif veya gecmis event listesi.
- `alarm_history`
  Alarm kayit gecmisi.

## Alan Alan Aciklama

### `ship`

Alanlar:

- `name`
  Gemi adi.
- `latitude`, `longitude`
  O anki koordinat.
- `speed_knots`
  Suya gore hiz.
- `speed_over_ground_knots`
  Zemine gore hiz.
- `heading_deg`
  Gemi burnunun baktigi yon.
- `course_over_ground_deg`
  Gercek hareket yonu.
- `fuel_percent`
  Yakit yuzu.
- `engine_rpm`
  Ana makine devri.
- `route_direction`
  `forward` veya `return`.
- `operation_mode`
  `underway`, `approach`, `harbor`, `berthed`, `departure` gibi modlar.
- `ship_role`
  `container`, `tanker`, `bulk` gibi tip.

### `navigation`

Alanlar:

- `speed_over_ground_knots`
- `speed_through_water_knots`
- `course_over_ground_deg`
- `heading_deg`
- `desired_heading_deg`
- `drift_angle_deg`
- `rate_of_turn_deg_min`
- `rudder_angle_deg`
- `turn_radius_nm`
- `eta_hours`
- `remaining_distance_nm`
- `next_waypoint_name`
- `distance_to_next_nm`
- `route_deviation_nm`
- `gps_satellites`
- `gps_hdop`
- `route_direction`
- `nav_status`

Anlamlari:

- `desired_heading_deg`
  Guidance sisteminin gitmek istedigi yon.
- `drift_angle_deg`
  heading ile gercek course arasindaki fark.
- `turn_radius_nm`
  Hesaplanmis donus yaricapi.
- `route_deviation_nm`
  Rota hattindan sapma.
- `nav_status`
  Navigasyon modu ozeti.

### `operations`

Alanlar:

- `operation_mode`
- `mission_status`
- `ship_role`
- `ship_class`
- `maneuvering_mode`
- `bow_thruster_active`
- `berth_ticks_remaining`
- `loading_progress_percent`
- `cargo_capacity`
- `cargo_unit`
- `length_m`
- `beam_m`

### `machinery`

Alanlar:

- `engine_load_percent`
- `shaft_power_kw`
- `fuel_flow_lph`
- `lube_oil_pressure_bar`
- `lube_oil_temp_c`
- `coolant_temp_c`
- `exhaust_temp_c`
- `turbo_rpm`
- `vibration_mm_s`
- `main_engine_status`
- `propulsion_mode`

Bu blok daha cok hesaplanmis sistem degerleri icindir. Ayrintili tekil sensor okumalari `sensors` altinda gelir.

### `power`

Alanlar:

- `generator_load_kw`
- `hotel_load_kw`
- `battery_voltage_v`
- `shore_power_connected`
- `emergency_bus_status`
- `bow_thruster_ready`

### `hull`

Alanlar:

- `draft_forward_m`
- `draft_aft_m`
- `trim_m`
- `roll_deg`
- `pitch_deg`
- `heel_deg`
- `ballast_percent`
- `bilge_level_percent`

### `cargo`

Alanlar:

- `cargo_utilization_percent`
- `cargo_amount`
- `cargo_unit`
- `reefer_containers_online`
- `freshwater_percent`
- `waste_tank_percent`
- `sludge_tank_percent`
- `cargo_mode`

### `environment`

Alanlar:

- `wave_height_m`
- `wind_speed_knots`
- `wind_direction_deg`
- `apparent_wind_knots`
- `visibility_nm`
- `depth_m`
- `water_temperature_c`
- `air_temperature_c`
- `humidity_percent`
- `barometric_pressure_hpa`
- `current_knots`
- `current_set_deg`
- `sea_state_beaufort`

### `meta`

Alanlar:

- `id`
- `name`
- `ship_name`
- `origin_port`
- `origin_country`
- `destination_port`
- `destination_country`
- `color`

### `route`

Alanlar:

- `waypoints`
  Rota uzerindeki tum waypoint listesi.
- `ports`
  Baslangic/bitis liman marker'lari.
- `deviation_nm`
  Bu snapshot icin sapma.
- `active_waypoint_index`
  Icinde bulunulan segmentin baslangic waypoint index'i.
- `next_waypoint_index`
  Hedeflenen sonraki waypoint index'i.
- `next_waypoint_name`
  Hedef waypoint adi.
- `remaining_distance_nm`
  Kalan rota mesafesi.

## `sensors` Objesi Nasil Calisir

`sensors`, key-value map'tir. Her key bir sensor kodudur:

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

Her sensor nesnesinde:

- `name`
  Sensorun kod adi.
- `value`
  Okuma degeri. String, number veya boolean olabilir.
- `unit`
  Birim bilgisi. Bazi sensorlerde `null` olabilir.
- `status`
  `OK`, `WARN`, `OFFLINE`

### Sensor Gruplari

Navigasyon sensorleri:

- `gps`
- `gps_position`
- `gps_satellites`
- `gps_hdop`
- `heading`
- `gyro_heading`
- `magnetic_compass`
- `course_over_ground`
- `speed_over_ground`
- `rate_of_turn`
- `speed_log`
- `track_error`
- `ais_transponder`
- `radar_range`
- `doppler_log`
- `depth_under_keel`
- `echo_sounder`
- `rudder_feedback`

Makine sensorleri:

- `shaft_power`
- `shaft_torque`
- `propeller_slip`
- `engine_load`
- `engine_temperature`
- `main_bearing_temp`
- `thrust_bearing_temp`
- `coolant_temp`
- `jacket_water_pressure`
- `jacket_water_inlet_temp`
- `lube_oil_pressure`
- `lube_oil_temp`
- `scavenge_air_pressure`
- `scavenge_air_temp`
- `governor_output`
- `turbo_rpm`
- `fuel_flow`
- `exhaust_temp`
- `vibration`
- `gearbox_oil_temp`
- `gearbox_oil_pressure`
- `stern_tube_temp`
- `engine_room_temp`
- `engine_room_humidity`
- `aux_blower_load`

Guc sensorleri:

- `generator_load`
- `hotel_load`
- `battery_bus`
- `shore_power`
- `emergency_bus`
- `thruster_status`
- `thruster_load`

Govde ve tank sensorleri:

- `bilge_level`
- `roll_sensor`
- `pitch_sensor`
- `heel_sensor`
- `draft_fore`
- `draft_aft`
- `trim_indicator`
- `hull_stress`
- `hull_bending`
- `torsion_index`
- `forepeak_tank`
- `aftpeak_tank`
- `freeboard_mid`
- `watertight_doors`
- `leak_watch`

Yuk ve servis tank sensorleri:

- `fuel`
- `fuel_total`
- `freshwater_tank`
- `waste_tank`
- `sludge_tank`
- `cargo_level`
- `reefer_power`
- `cargo_ops`

Dis etken sensorleri:

- `anemometer`
- `wind_direction_true`
- `barometer`
- `humidity_sensor`
- `air_temperature`
- `water_temperature`
- `current_meter`
- `current_set`
- `visibility_sensor`
- `sea_state`
- `depth`

## Alarm, Fault ve Event Yapilari

### `alerts[]`

Bir alert nesnesi:

```json
{
  "code": "engine_temp_warning",
  "level": "warning",
  "title": "Motor sicak",
  "message": "Motor sicakligi yukseliyor.",
  "value": 88.2,
  "unit": "C"
}
```

Alanlar:

- `code`
  Makine dostu kod.
- `level`
  `advisory`, `warning`, `critical`
- `title`
  Kisa baslik.
- `message`
  Kullaniciya gosterilecek aciklama.
- `value`
  Alarmi doguran deger.
- `unit`
  Birim.

### `faults[]`

Bir fault nesnesi:

```json
{
  "code": "low_oil_pressure",
  "title": "Low oil pressure",
  "severity": "critical",
  "status": "resolved",
  "message": "Yaglama basinci duzensiz.",
  "started_at": "2026-03-30T09:38:19.789855Z",
  "expected_end_at": null,
  "ended_at": "2026-03-30T09:38:28.595674Z",
  "effects": {
    "oil_pressure_delta_bar": -1.4,
    "fuel_flow_penalty": 0.06
  }
}
```

### `scenario_events[]`

Bir event nesnesi:

```json
{
  "code": "lagos_congestion",
  "kind": "port",
  "title": "Lagos Port Congestion",
  "severity": "advisory",
  "status": "active",
  "message": "Liman yaklasiminda trafige bagli hiz dususu.",
  "started_at": "2026-03-30T09:10:00Z",
  "ended_at": null,
  "start_tick": 42,
  "end_tick": 65
}
```

### `alarm_history[]`

Bir alarm history nesnesi:

```json
{
  "code": "fuel_warning",
  "level": "warning",
  "title": "Dusuk yakit",
  "status": "resolved",
  "started_at": "2026-03-30T09:00:00Z",
  "ended_at": "2026-03-30T09:05:00Z",
  "duration_ticks": 11,
  "last_value": 32.1,
  "unit": "percent"
}
```

## Hata Kodlari

Yaygin durumlar:

- `404 Fleet telemetry is not ready yet.`
  Simulasyon henuz ilk snapshot'i uretmedi.
- `404 Route not found.`
  Gecersiz `route_id`.

## Onerilen Client Akisi

Web veya mobil istemci icin onerilen sira:

1. `GET /fleet/routes`
   Listeyi ve route id'leri cek.
2. `GET /fleet/current`
   Ilk ekrani doldur.
3. `WS /ws/fleet`
   Canli akisa gec.
4. Gemi detay sayfasinda `GET /fleet/current/{route_id}`
   Tek gemi detayini cek.
5. Alarm ve incident ekranlarinda `GET /fleet/incidents`
   Fault/event/history verisini topla.

## Ornek route_id Degerleri

- `eurasia-corridor`
- `atlantic-bridge`
- `southern-arc`
- `arabian-link`
