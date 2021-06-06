from app import db

class Ioc(db.Model):
    def __init__(self, value, type, tlp, tag, source, added_on):
        self.value = value
        self.type = type
        self.tlp = tlp
        self.tag = tag
        self.source = source
        self.added_on = added_on

class Whitelist(db.Model):
    def __init__(self, element, type, source, added_on):
        self.element = element
        self.type = type
        self.source = source
        self.added_on = added_on

class MISPInst(db.Model):
    def __init__(self, name, url, key, ssl, source, added_on):
        self.name = name
        self.url = url
        self.apikey = key
        self.verifycert = ssl
        self.source = source
        self.added_on = added_on

db.mapper(Whitelist, db.Table('whitelist', db.metadata, autoload=True))
db.mapper(Ioc, db.Table('iocs', db.metadata, autoload=True))
db.mapper(MISPInst, db.Table('mispinstance', db.metadata, autoload=True))
