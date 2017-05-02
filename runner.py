from jenkins_source import Jenkins
from alert import Alert
from hue_light import HueLightController
from light import Light
import json
from jsonschema import validate, ValidationError
import syslog

class Runner():
    def __init__(self, cfg, hue_bridge, jenkins,
                 create_missing_lights=False):
        self._hue_bridge_ip = hue_bridge
        self._jenkins_ip = jenkins
        self._cfg_path = cfg
        self._create_missing_lights = create_missing_lights
        self.restart()
        print("Initialisation done")

    def restart(self):
        syslog.syslog('soft restart...')
        self._load_config(self._cfg_path)
        hue_controller = HueLightController(self._hue_bridge_ip)
        virtual_lights = [Light(**args) for args in self.cfg['virtual_lights']]
        lights = hue_controller.lights + virtual_lights
        jenkins = Jenkins(self._jenkins_ip)
        self.alerts = [self.create_alert(cfg, lights, jenkins, self._create_missing_lights) for cfg in self.cfg['alerts']]

    def update_alerts(self):
        for alert in self.alerts:
            alert.update()

    def _load_config(self, cfg_file_name):
        with open('alerts_cfg.schema.json') as schema_file:
            schema = json.load(schema_file)
        try:
            with open(cfg_file_name) as cfg_file:
                config = json.load(cfg_file)
            validate(config, schema)
        except:
            print("--- Error when reading config file {} ---".format(cfg_file_name))
            raise
        else:
            if 'virtual_lights' not in config:
                config['virtual_lights'] = []
            self.cfg = config

    def create_alert(self, alert_cfg, lights, jenkins, create_missing_lights=False):
        monitored_jobs = []
        num_ignored_fails = alert_cfg.get('num_ignored_fails', 0)
        ignored_jobs = alert_cfg.get('jobs_to_ignore', [])

        for name in alert_cfg['jobs_to_watch']:
            monitored_jobs += jenkins.get_jobs(name)

        monitored_jobs = [job for job in monitored_jobs if job.name not in ignored_jobs]

        print("{} watches {} jobs and allows {} fails".format(alert_cfg['light'], len(monitored_jobs), num_ignored_fails))
        if ignored_jobs:
            print("{} explicitly ignores {}".format(alert_cfg['light'], ",".join(ignored_jobs)))

        light = next((l for l in lights if l.name==alert_cfg['light']), None)
        if not light:
            print("Configured light {} does not exist".format(alert_cfg['light']))
            if not create_missing_lights:
                print("Available lights: {}".format(', '.join((l.name for l in lights))))
                exit(1)
            print("Creating virtual light {}".format(alert_cfg['light']))
            light = Light(name=alert_cfg['light'], enable_debug_print=True)

        alert = Alert([light], monitored_jobs, num_ignored_fails)
        print(alert)
        return alert
