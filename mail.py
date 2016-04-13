#!/usr/bin/python
# -*- coding: UTF-8 -*-

import smtplib
import time
import ConfigParser
import string, os, sys

from email.mime.text import MIMEText
import ceph_dash
from ceph_dash import CephApiConfig
from ceph_dash import CephClusterProperties
from ceph_dash import CephClusterCommand
from rados import Rados
from rados import ObjectNotFound
from rados import PermissionError
from rados import Error as RadosError

class MailSender:
    mail_user=''
    mail_pass=''
    mail_host="smtp.qq.com"
    mailto_list=[]

    def __init__(self, name, password):
        self.mail_user=name
	self.mail_pass=password

    def set_mailto(self, mailto):
	print mailto
        self.mailto_list=mailto

    def send_mail(self,context):
        me="<"+self.mail_user+">"
	msg=MIMEText(context,_subtype='html',_charset='gb2312')
	msg['Subject']='CEPH WARNING'
	msg['From']=me
	msg['To']=";".join(self.mailto_list)
	try:
            s=smtplib.SMTP()
	    s.connect(self.mail_host)
	    s.login(self.mail_user,self.mail_pass)
	    s.sendmail(me, self.mailto_list, msg.as_string())
	    s.close()
	    return True
        except Exception, e:
	    print str(e)
	    return False

class MailMonitor:

    def __init__(self):
        self.config = CephApiConfig()
        self.clusterprop = CephClusterProperties(self.config)
    
    def get_error_osd_info(self):
	with Rados(**self.clusterprop) as cluster:
	    cluster_status = CephClusterCommand(cluster, prefix='status', format='json')
       	    if 'err' in cluster_status:
	        return 'Can not get the ceph cluster status!'

            total_osds = cluster_status['osdmap']['osdmap']['num_osds']
	    in_osds = cluster_status['osdmap']['osdmap']['num_up_osds']
	    up_osds = cluster_status['osdmap']['osdmap']['num_in_osds']

	    if up_osds < total_osds or in_osds < total_osds:
	        osd_status = CephClusterCommand(cluster, prefix='osd tree', format='json')
	        if 'err' in osd_status:
                    return 'Can not get the osd status!'

                cluster_status['osdmap']['details'] = ceph_dash.get_unhealthy_osd_details(osd_status)
	        return cluster_status['osdmap']['details']
	    else:
		return '';

    def get_error_mon_info(self):
        with Rados(**self.clusterprop) as cluster:
            cluster_status = CephClusterCommand(cluster, prefix='status', format='json')
            monmap_mons = cluster_status['monmap']['mons']
            timecheck_mons = cluster_status['health']['timechecks']['mons']
            err_mons = monmap_mons[:]
            for monmap_mon in monmap_mons:
                for timecheck_mon in timecheck_mons:
                    if timecheck_mon['name'] == monmap_mon['name']:
                        err_mons.remove(monmap_mon)

        return err_mons

if __name__ == '__main__':
    mon = MailMonitor()
    cf = ConfigParser.ConfigParser()
    cf.read("mail.conf")
    user_name = cf.get("mail", "user_name")
    pass_word = cf.get("mail", "pass_word")
    mailto_list = cf.get("mail", "mailto").split(",")
    mail_sender = MailSender(user_name, pass_word)
    mail_sender.set_mailto(mailto_list)

    while True:
        osd_status = mon.get_error_osd_info()
        mon_status = mon.get_error_mon_info()
        if osd_status != '' or len(mon_status) > 0:
    	    context = "<table>"
	    context += "<tr>"
	    context += "<td style='width:100px'>status</td>"
	    context += "<td style='width:100px'>host</td>"
	    context += "<td style='width:100px'>name</td>"
	    context += "</tr>"
	    if type(osd_status)==list:
  	        for item in osd_status:
		    context += "<tr><td>"+item['status']+"</td><td>"+item['host']+"</td><td>"+item['name']+"</td></tr>"
	    else:
		context += "<tr><td colspan='3'>"+str(osd_status)+"</td></tr>"

            for mon in mon_status:
                context += "<tr><td>"+ "mon_error" +"</td><td>"+mon['addr']+"</td><td>"+mon['name']+"</td></tr>"
	    context += "</table>"
	    mail_sender.send_mail(str(context))
	time.sleep(300)
