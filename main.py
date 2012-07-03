#!/usr/bin/python
# -*- coding: utf-8 -*-
import tornado
import tornado.ioloop
import tornado.web
import tornado.httpserver
import sys,os
import tornado.database
from datetime import datetime
from time import localtime, strftime, strptime, mktime
import random
import json


class Ping(tornado.web.RequestHandler):
    def get(self):
        self.write('I\'m alive! :) <br /><br />')
        self.write('URI: ' + self.request.uri + '<br />')
        self.write('Verb: ' + self.request.method + '<br />')
        self.write('Host: ' + self.request.host + '<br />')
        db = createDbConnection()
        if db==None:
            self.write("Error while connecting to database.")
            return
        else:
            self.write("Database connection OK! <br />")

class Checkin(tornado.web.RequestHandler):
    def get(self):
        self.write('Host: ' + self.request.host + '<br />')
        self.write('To checkin, make a POST like /checkin?key=xxx&version=001&type=batch <br />')
    def post(self):
        db = createDbConnection()        
        try:
            sKey = self.get_argument('key')
            sType = self.get_argument('type')
            sVersion = self.get_argument('version')            
        except:
            self.write("ERROR: One or more arguments are missing.")
            return
        if db==None:
            self.write("Error while connecting to database.")
            return
        if sType=='batch':
            sUpdateTimeField = "lastCheckinBatch"
        elif sType=='lac':
            sUpdateTimeField = "lastCheckinLAC"
        else:
            self.write("ERROR: Unknown type.")
            return
        rowCount = db.execute_rowcount("SELECT * FROM customers WHERE id = %s", sKey) 
        if rowCount == 1:
            selectQ = """ UPDATE customers
                          SET %s = %%s, version = %%s
                          WHERE id = %%s""" % (sUpdateTimeField) #String substitute field name.
            db.execute(selectQ,strftime("%Y-%m-%d %H:%M:%S", localtime()), sVersion, sKey) #String subst the other query parameters and run query.
            self.write('Database updated. Checkin OK.')
        elif rowCount < 1:
            self.write('ERROR: CustomerID not found. Recieved: ' + sKey)
        elif rowCount > 1:
            self.write('ERROR: Multiple customers with identical ID. Recieved: ' + sKey)     
        else:
            self.write('Unknown error.')
            
            
        
        
class Customer(tornado.web.RequestHandler):
    def post(self):
        db = createDbConnection()
        if db==None:
            self.write("Error while connecting to database.")
            return
        try:
            sAdminUser  = self.get_argument('adminuser')
            sAdminPass  = self.get_argument('adminpass') 
            sName       = self.get_argument('name')
            sEmail      = self.get_argument('mail')
        except:
            self.write("ERROR: One or more arguments are missing.")
            return
        if isAdmin(sAdminUser, sAdminPass):
            #Name required and shall be unique.
            if sName <> "":    
                if db.execute_rowcount("SELECT * FROM customers WHERE name = %s", (sName)) == 0:
                    #OK, create customer in database.
                    newKey = os.urandom(20).encode('hex')
                    db.execute("INSERT INTO customers (id,name,notificationEmail) VALUES (%s, %s, %s)", newKey, sName, sEmail)
                    self.write('<p>Customer ' + sName + ' with ID ' + newKey + ' created.</p>')
                else:
                    self.write("<p>Customer name already exists in database.</p>")
                    return    
        else:
            self.write("Access denied.")    
    def get(self):
        db = createDbConnection()
        if db==None:
            self.write("Error while connecting to database.")
            return    
        #List all customers and return JSON formatted. (Date_handler hack for datetime to string conversion.) 
        #for customer in json.JSONEncoder(default=date_handler).iterencode(db.query("SELECT * from customers")):
        #Scrap json, return html table.
        self.write("<div id='timeLastUpdated'>" + strftime("%Y-%m-%d %H:%M:%S", localtime()) + "</div>") #hidden, may be used in future.
        self.write("<table class='customerList'>")
        self.write("<tr><th>KUND</th><th>BATCH MINUTER SEN CHECKIN</th><th>LAC MINUTER SEN CHECKIN</th>")
        self.write("<th>VERSION</th></tr>")
        #List all customers and the time for their last checkin.
        for customer in db.query("SELECT * FROM customers ORDER BY customers.lastCheckinBatch DESC"):
            cssClass, batchTimeDiffMin, lacTimeDiffMin = Customer.customerCssClass(self,customer.lastCheckinBatch, customer.lastCheckinLAC)			
            batchTimeDiffString = "{0:.0f}".format(round(batchTimeDiffMin))
            lacTimeDiffString = "{0:.0f}".format(round(lacTimeDiffMin))
            if batchTimeDiffString=="9999":
                batchTimeDiffString = ""
            if lacTimeDiffString=="9999":
                lacTimeDiffString = ""
            self.write("<tr class='" + cssClass + "'>")
            self.write("<td>" + customer.name + "</td>")
            self.write("<td>" + batchTimeDiffString + "</td>") #Minutes since last checkin (batch).
            self.write("<td>" + lacTimeDiffString + "</td>") #Minutes since last checkin (LAC).
            self.write("<td>" + str(customer.version) + "</td>")            
            self.write("</tr>")
        self.write("</table>")
    
    def customerCssClass(self,lastCheckinBatch, lastCheckinLAC):
        ### Return class according to time diff. ###
        if lastCheckinBatch==None and lastCheckinLAC==None:
            return ("red",9999,9999)
        elif lastCheckinBatch!=None and lastCheckinLAC==None: #LAC not used.
		    #Stupid datetime conversion.
            lastCheckinBatch = strptime(str(lastCheckinBatch), "%Y-%m-%d %H:%M:%S")
            timeDifferenceBatch = mktime(localtime()) - mktime(lastCheckinBatch)
            timeDiffMinBatch = timeDifferenceBatch/60.0            
            if timeDiffMinBatch < 0:
                return ("blue", timeDiffMinBatch,9999) #Time traveling are we?  
            elif timeDiffMinBatch > 60:
                return ("red", timeDiffMinBatch,9999)
            elif timeDiffMinBatch > 30:
                return ("orange", timeDiffMinBatch,9999)
            elif timeDiffMinBatch > 15:
                return ("yellow", timeDiffMinBatch,9999)
            else:
                return ("green", timeDiffMinBatch,9999)
        else:
		    #Both batch and LAC used.			
            lastCheckinBatch = strptime(str(lastCheckinBatch), "%Y-%m-%d %H:%M:%S")
            timeDifferenceBatch = mktime(localtime()) - mktime(lastCheckinBatch)
            timeDiffMinBatch = timeDifferenceBatch/60.0
            lastCheckinLAC = strptime(str(lastCheckinLAC), "%Y-%m-%d %H:%M:%S")
            timeDifferenceLAC = mktime(localtime()) - mktime(lastCheckinLAC)
            timeDiffMinLAC = timeDifferenceLAC/60.0        
            if timeDiffMinBatch < 0 or timeDiffMinBatch < 0: #thefuck? 
                return ("blue", timeDiffMinBatch,timeDiffMinLAC) 
            elif timeDiffMinBatch > 60 or timeDiffMinBatch > 60:
                return ("red", timeDiffMinBatch,timeDiffMinLAC)
            elif timeDiffMinBatch > 30 or timeDiffMinBatch > 30:
                return ("orange", timeDiffMinBatch,timeDiffMinLAC)
            elif timeDiffMinBatch > 15 or timeDiffMinBatch > 15:
                return ("yellow", timeDiffMinBatch,timeDiffMinLAC)
            else:
                return ("green", timeDiffMinBatch,timeDiffMinLAC)
        
        
            
class CreateUser(tornado.web.RequestHandler):
    def post(self):
        self.write('Create user called.')        
    def get(self):
        self.write('Get user called.')

class DoLogin(tornado.web.RequestHandler): #Unfinished.
    def post(self):
        db = createDbConnection()
        if db==None:
            self.write("Error while connecting to database.")
            return
        try:
            sUser  = self.get_argument('user')
            sPass  = self.get_argument('pass') 
        except:
            self.write("ERROR: One or more arguments are missing.")
            return
        if sUser != "" and sPass != "":
            if db.execute_rowcount("SELECT * FROM users WHERE id = %s AND password = %s AND isAdmin = 1", sUser, sPass) > 0:
                self.write('True')
                return
            else:
                self.write('Username or password incorrect.')
                return         
            
            
def createDbConnection():
    try:
        db = tornado.database.Connection("localhost", "lnm", user="lnm", password="LaxHax!")
    except MySQLdb.Error, e:
         #self.write("Error %d: %s" % (e.args[0], e.args[1]))
         return None
    return db     
         
def isAdmin(user,password):
    db = createDbConnection()
    if db==None:
        self.write("Error while connecting to database.")
        return False
    if db.execute_rowcount("SELECT * FROM users WHERE id = %s AND password = %s AND isAdmin = 1", user, password) > 0:
        return True
    else:
        return False
        
def date_handler(obj): #Extension for json datetime conversion.
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj    

settings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static"),    
}
application = tornado.web.Application([	
	(r'/(favicon.ico)', tornado.web.StaticFileHandler, dict(path=settings['static_path'])),
    (r"/static/(.*)", tornado.web.StaticFileHandler, dict(path=settings['static_path'])),    	
	(r"/ping", Ping),
    (r"/checkin", Checkin),
    (r"/customer", Customer),
    (r"/createuser", CreateUser),
    (r"/dologin", DoLogin)	
],debug=False)

if __name__ == "__main__":
    application.listen(8888)           
    tornado.ioloop.IOLoop.instance().start()
    
    
