#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# Snips Heizung + Homeassistant
# -----------------------------------------------------------------------------
# Copyright 2019 Patrick Fial
# -----------------------------------------------------------------------------
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and 
# associated documentation files (the "Software"), to deal in the Software without restriction, 
# including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, 
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial 
# portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT 
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. 
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE 
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------

import io
import toml
import requests
import logging
import json
from os import environ

from snipsTools import SnipsConfigParser
from hermes_python.hermes import Hermes
from hermes_python.ontology import *

# -----------------------------------------------------------------------------
# global definitions (home assistant service URLs)
# -----------------------------------------------------------------------------

HASS_GET_STATE_SVC = "/api/states/"
HASS_HEAT_ON_SVC = "/api/services/climate/turn_on"
HASS_HEAT_OFF_SVC = "/api/services/climate/turn_off"
HASS_SET_TEMP_SVC = "/api/services/climate/set_temperature"

APP_ID = "snips-skill-s710-heating"

# -----------------------------------------------------------------------------
# class App
# -----------------------------------------------------------------------------

class App(object):

    # -------------------------------------------------------------------------
    # ctor

    def __init__(self, debug = False):

        self.logger = logging.getLogger(APP_ID)
        self.debug = debug

        # parameters

        self.mqtt_host = "localhost:1883"
        self.mqtt_user = None
        self.mqtt_pass = None

        self.hass_host = None
        self.hass_token = None

        self.known_intents = ['s710:isHeatingOn','s710:enableHeating','s710:disableHeating','s710:setTemperature']

        # read config.ini

        try:
            self.config = SnipsConfigParser.read_configuration_file("config.ini")
        except Exception as e:
            print("Failed to read config.ini ({})".format(e))
            self.config = None

        try:
            self.read_toml()
        except Exception as e:
            print("Failed to read /etc/snips.toml ({})".format(e))

        # try to use HASSIO token via environment variable & internal API URL in case no config.ini parameters are given

        if 'hass_token' in self.config['secret']:
            self.hass_token = self.config['secret']['hass_token']
        elif 'HASSIO_TOKEN' in environ:
            self.hass_token = environ['HASSIO_TOKEN']

        if 'hass_host' in self.config['global']:
            self.hass_host = self.config['global']['hass_host']
        elif self.hass_token is not None and 'HASSIO_TOKEN' in environ:
            self.hass_host = 'http://hassio/homeassistant/api'

        self.hass_headers = { 'Content-Type': 'application/json', 'Authorization': "Bearer " + self.hass_token }

        if 'entity_dict' in self.config['global']:
            try:
                self.entity_dict = json.loads(self.config['global']['entity_dict'])
            except Exception as e:
                self.logger.error('Failed to parse entity-dictionary ({})'.format(e))
                self.entity_dict = {}
        else:
            self.entity_dict = {}

        if self.debug:
            print("Connecting to {}@{} ...".format(self.mqtt_user, self.mqtt_host))

        self.start()

    # -----------------------------------------------------------------------------
    # read_toml

    def read_toml(self):
        snips_config = toml.load('/etc/snips.toml')
    
        if 'mqtt' in snips_config['snips-common'].keys():
            self.mqtt_host = snips_config['snips-common']['mqtt']

        if 'mqtt_username' in snips_config['snips-common'].keys():
            self.mqtt_user = snips_config['snips-common']['mqtt_username']

        if 'mqtt_password' in snips_config['snips-common'].keys():
            self.mqtt_pass = snips_config['snips-common']['mqtt_password']

    # -------------------------------------------------------------------------
    # start

    def start(self):
        with Hermes(mqtt_options = MqttOptions(broker_address = self.mqtt_host, username = self.mqtt_user, password = self.mqtt_pass)) as h:
            h.subscribe_intents(self.on_intent).start()

    # -------------------------------------------------------------------------
    # on_intent

    def on_intent(self, hermes, intent_message):
        intent_name = intent_message.intent.intent_name
        room_id = intent_message.site_id
        temperature = None

        # extract mandatory information (lamp_id, room_id)

        try:
            if len(intent_message.slots):
                if len(intent_message.slots.location):
                    room_id = intent_message.slots.location.first().value
                    room_id = room_id.lower().replace('ä', 'ae').replace('ü','ue').replace('ö', 'oe')
                if len(intent_message.slots.temperature):
                    temperature = int(intent_message.slots.temperature.first().value)
        except:
            pass

        # ignore unknown/unexpected intents

        if intent_name not in self.known_intents:
            return None

        self.process(hermes, intent_message, intent_name, room_id, temperature)

    # -------------------------------------------------------------------------
    # process

    def process(self, hermes, intent_message, intent_name, room_id, temperature):
        if room_id not in self.entity_dict:
            self.logger.error('Room "{}" not known, cannot determine entity_id. Must skip request.'.format(room_id))
            return self.done(hermes, intent_message, 'Unbekannter Raum')

        entity_id = self.entity_dict[room_id]

        if intent_name == 's710:isHeatingOn':
            r = requests.get(self.hass_host + HASS_GET_STATE_SVC + entity_id, headers = self.hass_headers)

            # evaluate service response & send snips reply

            if r.status_code != 200:
                self.logger.error('REST API call failed ({}/{})'.format(r.status_code, r.content.decode('utf-8')[:80]))
                self.done(hermes, intent_message, 'Fehler')
            else:
                try:
                    response = json.loads(r.content.decode('utf-8'))
                except Exception as e:
                    self.logger.error('Failed to parse REST API response ({}/{})'.format(e, r.content.decode('utf-8')[:80]))
                    return self.done(hermes, intent_message, 'Fehler')

                if 'state' not in response or response['state'] == 'off':
                    return self.done(hermes, intent_message, 'Nein, die Heizung ist aus.')

                temp = None

                if 'attributes' in response and 'temperature' in response['attributes']:
                    temp = str(response['attributes']['temperature'])
                    return self.done(hermes, intent_message, 'Ja, die Heizung ist an auf ' + temp + ' Grad.')

                return self.done(hermes, intent_message, 'Ja, die Heizung ist an.')
        else:
            r = None
            data = { "entity_id": entity_id }
            text = None

            if intent_name == 's710:enableHeating':
                r = requests.post(self.hass_host + HASS_HEAT_ON_SVC, json = data, headers = self.hass_headers)
                text = 'Heizung eingeschaltet.'

                if r.status_code == 200 and temperature:
                    data['temperature'] = temperature
                    r = requests.post(self.hass_host + HASS_SET_TEMP_SVC, json = data, headers = self.hass_headers)
                    text = 'Heizung eingeschaltet auf ' + str(temperature) + ' Grad.'
                
            elif intent_name == 's710:disableHeating':
                r = requests.post(self.hass_host + HASS_HEAT_OFF_SVC, json = data, headers = self.hass_headers)
                text = 'Heizung ausgeschaltet.'
            elif intent_name == 's710:setTemperature':
                data['temperature'] = temperature
                r = requests.post(self.hass_host + HASS_SET_TEMP_SVC, json = data, headers = self.hass_headers)
                text = 'Temperatur auf ' + str(temperature) + ' gestellt.'
            else:
                print("Intent {}/parameters not recognized, ignoring".format(intent_name))
                return

            # evaluate service response & send snips reply

            if r.status_code != 200:
                self.logger.error('REST API call failed ({}/{})'.format(r.status_code, r.content.decode('utf-8')[:80]))
                self.done(hermes, intent_message, 'Fehler')
            else:
                self.done(hermes, intent_message, text)

    # -------------------------------------------------------------------------
    # done

    def done(self, hermes, intent_message, response):
        if hermes and intent_message:
            hermes.publish_end_session(intent_message.session_id, response)
        else:
            self.logger.info(response)
            print(response)

# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    app = App()

    #app.process(None, None, "s710:isHeatingOn", "wohnzimmer", None)
    #app.process(None, None, "s710:enableHeating", "wohnzimmer", 22.5)
