# Snips Heizung + Homeassistant

App zur Sprachsteuerung der Heizung / Climate-Komponente über Home Assistant (https://www.home-assistant.io/). Nutzt die Home Assistant REST API. 

## Installation

#### 1) Home Assistant Access Token anlegen

Im Home Assistant Web-GUI auf das Profil klicken, und dort (siehe auch: https://www.home-assistant.io/docs/authentication/#your-account-profile) unter **Long-Lived Access Tokens** einen Token erstellen. Dieser wird als Konfigurationsparameter für die Snips-App benötigt.

#### 2) Installation der Snips-App

Installation der Lights + Homeassistant App aus dem Store: https://console.snips.ai/store/de/skill_3a8pwgxAyK5

#### 3) Assistant via `sam` installieren/aktualisieren

# Parameter

Die App bentöigt die folgenden Parameter:

- `entity_dict`: Ein JSON-Dictionary mit dem Mapping aus Raumname und Entity-ID (z.b. `{"wohnzimmer":"climate.eurotronic_eur_spiritz_wall_radiator_thermostat_heat_4"}`)
- `hass_host`: Hostname der Home Assistant Installation inkl. Protokoll und Port (z.b. `http://10.0.0.5:8123`)
- `hass_token`: Der Access-Token der in Schritt Installation/1) erstellt wurde

# Funktionen

Die App umfasst folgende Intents:

- `s710:isHeatingOn` - Abfrage ob die Heizung in einem Raum an oder aus ist
- `s710:enableHeating` - Einschalten der Heizung in einem Raum (optional mit Temperatur)
- `s710:disableHeating` - Ausschalten der Heizung in einem Raum
- `s710:setTemperature` - Setzen der Temperatur einer Heizung

Die App nutzt die Services `climate.turn_on`, `climate.turn_off`, `climate.set_temperature` sowie `GET:/api/states`. Es wird jeweils eine gültige Entity-ID der gewünschten Climate-Komponente benötigt, andernfalls funktioniert der Service-Call nicht.
