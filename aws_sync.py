import appdaemon.appapi as appapi
import yaml
from datetime import datetime, date, time
import boto3
import io

class AwsSync(appapi.AppDaemon):
    def initialize(self):
        #process = subprocess.Popen(["tail", "/home/homeassistant/config/appdaemon/log"], stdout=subprocess.PIPE)
		#output, err = process.communicate()
		#self.log("{} -> {}".format(output,err))
        self.log("Initializing AWS Logger")
        time = self.datetime()
        with open("/home/homeassistant/scripts/log_sync_config.yaml", 'r') as stream:
            log_sync_config = yaml.load(stream)
        with open("/home/homeassistant/config/aws_logging.yaml", 'r') as stream:
            self.log_sync_time = yaml.load(stream)
        username_file = open("/home/homeassistant/config/email.txt")
        self.username = username_file.read().strip()
        self.log_handles = {}
        for log_name in log_sync_config['logs']:
            self.log_handles[log_name] = self.run_every(self.upload_log, time, log_sync_config['logs'][log_name]['time_interval'], log = log_sync_config['logs'][log_name], snyc_time = self.log_sync_time[log_name])
        self.s3 = boto3.client('s3',aws_access_key_id=log_sync_config['aws']['ACCESS_KEY'],aws_secret_access_key=log_sync_config['aws']['SECRET_KEY'])
        self.log(str(self.s3))

    def upload_log(self, kwargs):
        log_name = kwargs['log']['log_name']
        location = kwargs['log']['location']
        timestamp_format = kwargs['log']['timestamp_format']
        timestamp_start = kwargs['log']['timestamp_start']
        timestamp_end = kwargs['log']['timestamp_end']
        last_updated = kwargs['snyc_time']['last_updated']
        self.log("Uploading {} to AWS".format(log_name))
        upload_name = "{}/{}/{}".format(self.username,log_name,self.datetime().isoformat()[0:19])
        newLog = str()
        with open(location, 'r') as stream:
            for line in stream:
                #self.log(line)
                try:
                    line_timestamp = datetime.strptime(line[timestamp_start:timestamp_end], timestamp_format)
                except ValueError:
                    newLog += line
                    if not line.endswith('\n'):
                        newLog += '\n'
                if line_timestamp>last_updated:
                    newLog += line
                    if not line.endswith('\n'):
                        newLog += '\n'
                else:
                    newLog = str()
        if newLog == str():
            self.log("No new Data in {}".format(log_name))
            return
        self.s3.put_object(Body =newLog, Bucket ='pi-client-logs',Key = upload_name)
        self.log_sync_time[log_name]['last_updated'] = self.datetime()
        with io.open('/home/homeassistant/config/aws_logging.yaml', 'w', encoding='utf8') as outfile:
            yaml.dump(self.log_sync_time, outfile, default_flow_style=False, allow_unicode=True)
        self.log("Upload {} Complete".format(log_name))
