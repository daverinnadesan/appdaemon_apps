import appdaemon.appapi as appapi 
import yaml
import io
import datetime
import re



class AthenaActivities(appapi.AppDaemon):
	"""Event Listener for Telegram bot events"""
	def initialize(self):
			self.log("AthenaActivities Initialized...")
			self.averageDays = 2
			with open("/home/homeassistant/config/appdaemon/appdaemon_apps/activities.yaml", 'r') as stream:
				self.activities = yaml.load(stream)
			with open("/home/homeassistant/config/appdaemon/appdaemon_apps/activityLog.yaml", 'r') as stream:
				self.history = yaml.load(stream)

#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

	def execute(self, payload_event):
		self.log("Executing {}".format(payload_event))
		for regex in OPTIONS_TO_METHOD.keys():
			p = re.compile(regex)
			m =  p.match(payload_event['text'])
			if m:
				self.log(m.groups())	
				return OPTIONS_TO_METHOD[regex](self,payload_event,m)
		self.log("Activity Option not found")
		self.telegramSendError("Activity Option not found")
		return False

#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

	def reset(self, payload_event, match):
			count = 0
			for activity in self.activities['activities']:
					self.activities['activities'][count]['score'] = 0
					count+=1
			self.writeChanges(self.activities)
			self.call_service("telegram_bot/send_message",
				target = 444908880,
				message = "Reset Complete",
				keyboard= ['List,View', 'Do', 'Edit', 'Delete', '<Reset>'])

#***************************************************************************************************************************************

	def activityDetail(self, payload_event, match):
			activity_text = match.group("activity_name")
			activity_names = [x['name'].lower() for x in self.activities['activities']]
			if activity_text not in activity_names:
					self.log("Activity Not Found")
					self.telegramSendError("Activity Not found")
					return False
			else:
					activity = self.activities['activities'][activity_names.index(activity_text)]
					saturation = activity['score']/activity['frequencyFactor']*100
					message ="<code>{:10}</code>{}\n\n".format("[{:.2f}]".format(saturation), activity['name'])
					for item in activity.items():
							if item[0] not in ['name','score']:
								item = self.shorten(item)
								message += ("<code>{:10}</code>:{}\n".format(item[0],item[1]))
					keyboard = list()
					keyboard.append("Do {}".format(activity['name']))
					keyboard.append("Edit {}".format(activity['name']))
					keyboard.append("Delete {}".format(activity['name']))
					self.call_service("telegram_bot/send_message",
						target = 444908880,
						message = message,
						keyboard= keyboard)
					return True
						
	#***************************************************************************************************************************************
	def doOnly(self, payload_event, match):
			self.doRange(range(0,5))
	def doMore(self, payload_event, match):
			self.doRange(range(5,10))

	def list(self, payload_event, match):
			self.doRange(range(0,len(self.activities['activities'])))

	def doRange(self, activityRange):
			sortedList = sorted(self.activities['activities'], key=lambda x: x['score']/x['frequencyFactor'])
			stringList = ""
			keyboard = []
			for i in activityRange:
				activity = sortedList[i]
				saturation = activity['score']/activity['frequencyFactor']*100
				stringList+=("<code>{:10}</code>|  {}\n".format("[{:.2f}]".format(saturation), activity['name']))
				keyboard.append("Do {}".format(activity['name']))
			keyboard.append("Do, Do More")
			keyboard.append("List")
			#self.log(stringList)
			self.call_service("telegram_bot/send_message",
				target = 444908880,
				message = stringList,
				keyboard = keyboard)

	#***************************************************************************************************************************************	

	def do(self, payload_event, match):
			count = 0
			activity_text = match.group("activity_name")
			self.log("<{}>".format(activity_text))
			activity_names = [x['name'].lower() for x in self.activities['activities']]
			if activity_text not in activity_names:
					self.log("Activity Not Found")
					self.telegramSendError("Activity Not found")
					return False
			else:
					activity_do = self.activities['activities'][activity_names.index(activity_text)]
					oldScore = activity_do['score'] 
					newScore = oldScore + activity_do['frequencyFactor']
					oldSaturation = oldScore/activity_do['frequencyFactor']*100
					newSaturation = newScore/activity_do['frequencyFactor']*100
					self.activities['activities'][activity_names.index(activity_text)]['score'] = newScore
					self.logActivity(activity_do)
					n = self.calculateN()
					self.log("NEW n - <{}>".format(n))
					count = 0
					for activity in self.activities['activities']:
							if activity['name'] != activity_do['name']:
								newScore = activity['score'] - 1.0/n
								self.activities['activities'][count]['score'] = float("{0:.5f}".format(newScore))
							count+=1
					message = self.printActivity(activity_do)
					message += "{:>8}  \n<code>[{:.2f}] -> [{:.2f}]</code>".format(activity_do['name'],oldSaturation, newSaturation)
					self.call_service("telegram_bot/send_message",
						target = 444908880,
						message = message)
					self.writeChanges(self.activities)
					return True

	def calculateN(self):
			fromAverageDate = datetime.datetime.now() - datetime.timedelta(days = self.averageDays)
			activitiesForDaysCount = float()
			if self.history is None:
  				self.log("ERROR HISTORY NULL")
  				return 10
			for activity in self.history:
				if activity['timeCompleted']>fromAverageDate:
					activitiesForDaysCount += 1
			self.log("Total Activites over ({}) days - {}".format(self.averageDays, activitiesForDaysCount))
			n = activitiesForDaysCount/self.averageDays
			return n

	def logActivity(self, activity):
		if self.history is None:
			self.history = list()
		self.history.append({'name': activity['name'],'timeCompleted': datetime.datetime.now()})
		with io.open('/home/homeassistant/config/appdaemon/appdaemon_apps/activityLog.yaml', 'w', encoding='utf8') as outfile:
			yaml.dump(self.history, outfile, default_flow_style=False, allow_unicode=True)
#----------------------------------------------------------------------------------------------------------------------------------------------

	def writeChanges(self, write):
		self.log("Writing to  {}".format("activities.yaml"))
		with io.open("/home/homeassistant/config/appdaemon/appdaemon_apps/activities.yaml", 'w', encoding='utf8') as outfile:
			yaml.dump(write, outfile, default_flow_style=False, allow_unicode=True)

	def shorten(self, item):
		if item[0]=='time':
			return item[0],"{}:{}".format(item[1]['hours'],item[1]['minutes'])
		elif len(item[0])>10:
				shortName = item[0][0].upper()
				for i in item[0][1:]:
					if str(i).isupper():
							shortName+=i
				return shortName, item[1]
		return item

#-----------------------------------------------------------------------------------------

	def activityAdd(self, payload_event, match):
  		self.log("ADD")
	def activityEdit(self, payload_event, match):
  		self.log("EDIT")
	def activityDelete(self, payload_event, match):
  		self.log("DELETE")
	def activityDetail(self, payload_event, match):
  		self.log("DETAIL")

#-----------------------------------------------------------------------------------------	

	def telegramSendError(self, errorMessage):
		self.call_service("telegram_bot/send_message",
			target = 444908880,
			message = errorMessage)	
						

OPTIONS_TO_METHOD = {
	r'(?:activities\s)?(?:add|a)\s(?P<frequencyFactor>\d+)\s\w+$': AthenaActivities.activityAdd, 
	r'(?:activities\s)?(?:edit|e)\s\w+\s\w+\s\w+$': AthenaActivities.activityEdit,
	r'(?:activities\s)?(?:remove|r)(?P<activity_name>((\s|-)?\w)*)$': AthenaActivities.activityDelete,
	r'(?:activities\s)?(?:list|l)$': AthenaActivities.list, #Done
	r'(athena|(?:activities\s)?(?:do|d))$': AthenaActivities.doOnly, #Done
	r'(?:activities\s)?(?:do|d)\smore$': AthenaActivities.doMore, #Done
	r'(?:activities\s)?(?:do|d)\s(?P<activity_name>((\s|-)?\w)*)$': AthenaActivities.do, #Done
	r'(?:activities\s)?(?:meta|m)\s(?P<activity_name>((\s|-)?\w)*)$': AthenaActivities.activityDetail 
}