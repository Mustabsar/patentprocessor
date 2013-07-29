from sqlalchemy import func
from sqlalchemy import Column, Date, Integer, Float
from sqlalchemy import ForeignKey, Index
from sqlalchemy import Unicode, UnicodeText
from sqlalchemy.orm import deferred, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.declarative import declarative_base
from unidecode import unidecode

from sqlalchemy import Table

# Extend the Base >>>>>>
Base = declarative_base()
cascade = "all, delete, delete-orphan"


def init(self, *args, **kwargs):
    for i, arg in enumerate(args):
        self.__dict__[self.kw[i]] = arg
    for k, v in kwargs.iteritems():
        self.__dict__[k] = v

# tried this, but it doesn't seem to work.
# i think these must trigger something
# def update(self, **kwargs):
#     for k in kwargs:
#         self.__dict__[k] = kwargs.get(k)

Base.__init__ = init
# Base.update = update
# <<<<<<


# ASSOCIATION ----------------------

patentassignee = Table(
    'patent_assignee', Base.metadata,
    Column('patent_id', Unicode(20), ForeignKey('patent.id')),
    Column('assignee_id', Unicode(36), ForeignKey('assignee.id')))

patentinventor = Table(
    'patent_inventor', Base.metadata,
    Column('patent_id', Unicode(20), ForeignKey('patent.id')),
    Column('inventor_id', Unicode(36), ForeignKey('inventor.id')))

patentlawyer = Table(
    'patent_lawyer', Base.metadata,
    Column('patent_id', Unicode(20), ForeignKey('patent.id')),
    Column('lawyer_id', Unicode(36), ForeignKey('lawyer.id')))

locationassignee = Table(
    'location_assignee', Base.metadata,
    Column('location_id', Unicode(256), ForeignKey('location.id')),
    Column('assignee_id', Unicode(36), ForeignKey('assignee.id')))

locationinventor = Table(
    'location_inventor', Base.metadata,
    Column('location_id', Unicode(256), ForeignKey('location.id')),
    Column('inventor_id', Unicode(36), ForeignKey('inventor.id')))

# PATENT ---------------------------


class Patent(Base):
    __tablename__ = "patent"
    id = Column(Unicode(20), primary_key=True)
    type = Column(Unicode(20))
    number = Column(Unicode(64))
    country = Column(Unicode(20))
    date = Column(Date)
    abstract = deferred(Column(UnicodeText))
    title = deferred(Column(UnicodeText))
    kind = Column(Unicode(10))
    claims = Column(Integer)

    application = relationship("Application", uselist=False, backref="patent", cascade=cascade)
    classes = relationship("USPC", backref="patent", cascade=cascade)
    ipcrs = relationship("IPCR", backref="patent", cascade=cascade)

    rawassignees = relationship("RawAssignee", backref="patent", cascade=cascade)
    rawinventors = relationship("RawInventor", backref="patent", cascade=cascade)
    rawlawyers = relationship("RawLawyer", backref="patent", cascade=cascade)

    otherreferences = relationship("OtherReference", backref="patent", cascade=cascade)
    citations = relationship(
        "Citation",
        primaryjoin="Patent.id == Citation.patent_id",
        backref="patent", cascade=cascade)
    citedby = relationship(
        "Citation",
        primaryjoin="Patent.id == Citation.citation_id",
        backref="citation")
    usreldocs = relationship(
        "USRelDoc",
        primaryjoin="Patent.id == USRelDoc.patent_id",
        backref="patent", cascade=cascade)
    relpatents = relationship(
        "USRelDoc",
        primaryjoin="Patent.id == USRelDoc.rel_id",
        backref="relpatent")
    assignees = relationship("Assignee", secondary=patentassignee, backref="patents")
    inventors = relationship("Inventor", secondary=patentinventor, backref="patents")
    lawyers = relationship("Lawyer", secondary=patentlawyer, backref="patents")

    __table_args__ = (
        Index("pat_idx1", "type", "number", unique=True),
        Index("pat_idx2", "date"),
    )

    def stats(self):
        return {
            "classes": len(self.classes),
            "ipcrs": len(self.ipcrs),
            "rawassignees": len(self.rawassignees),
            "rawinventors": len(self.rawinventors),
            "rawlawyers": len(self.rawlawyers),
            "otherreferences": len(self.otherreferences),
            "citations": len(self.citations),
            "citedby": len(self.citedby),
            "usreldocs": len(self.usreldocs),
            "relpatents": len(self.relpatents),
        }

    def __repr__(self):
        return "<Patent('{0}, {1}')>".format(self.number, self.date)


class Application(Base):
    __tablename__ = "application"
    uuid = Column(Unicode(36), primary_key=True)
    patent_id = Column(Unicode(20), ForeignKey("patent.id"))
    type = Column(Unicode(20))
    number = Column(Unicode(64))
    country = Column(Unicode(20))
    date = Column(Date)
    __table_args__ = (
        Index("app_idx1", "type", "number"),
        Index("app_idx2", "date"),
    )

    def __repr__(self):
        return "<Application('{0}, {1}')>".format(self.number, self.date)


# SUPPORT --------------------------


class RawLocation(Base):
    __tablename__ = "rawlocation"
    id = Column(Unicode(256), primary_key=True)
    location_id = Column(Unicode(256), ForeignKey("location.id"))
    city = Column(Unicode(128))
    state = Column(Unicode(10), index=True)
    country = Column(Unicode(10), index=True)
    rawinventors = relationship("RawInventor", backref="rawlocation")
    rawassignees = relationship("RawAssignee", backref="rawlocation")
    __table_args__ = (
        Index("loc_idx1", "city", "state", "country"),
    )

    @hybrid_property
    def address(self):
        addy = []
        if self.city:
            addy.append(self.city)
        if self.state:
            addy.append(self.state)
        if self.country:
            addy.append(self.country)
        return u", ".join(addy)

    # -- Functions for Disambiguation --

    @hybrid_property
    def summarize(self):
        return {
            "city": self.city,
            "state": self.state,
            "country": self.country}

    @hybrid_property
    def uuid(self):
        return self.id

    @hybrid_property
    def __clean__(self):
        return self.location

    @hybrid_property
    def __related__(self):
        return Location

    def unlink(self, session):
        clean = self.__clean__
        clean.__raw__.pop(clean.__raw__.index(self))

        clean.assignees = [obj.patent for obj in clean.__raw__]
        clean.inventors = [obj.rawlocation.location for obj in clean.__raw__ if obj.rawlocation.location]
        clean.assignees = list(set(clean.assignees))
        clean.inventors = list(set(clean.inventors))

    # ----------------------------------

    def __repr__(self):
        return "<RawLocation('{0}')>".format(unidecode(self.address))


class Location(Base):
    __tablename__ = "location"
    id = Column(Unicode(256), primary_key=True)
    city = Column(Unicode(128))
    state = Column(Unicode(10), index=True)
    country = Column(Unicode(10), index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    assignees = relationship("Assignee", secondary=locationassignee, backref="locations")
    inventors = relationship("Inventor", secondary=locationinventor, backref="locations")
    rawlocations = relationship("RawLocation", backref="location")
    __table_args__ = (
        Index("dloc_idx1", "latitude", "longitude"),
        Index("dloc_idx2", "city", "state", "country"),
    )

    @hybrid_property
    def address(self):
        addy = []
        if self.city:
            addy.append(self.city)
        if self.state:
            addy.append(self.state)
        if self.country:
            addy.append(self.country)
        return u", ".join(addy)

    # -- Functions for Disambiguation --

    @hybrid_property
    def summarize(self):
        return {
            "id": self.id,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude}

    @hybrid_property
    def __raw__(self):
        return self.rawlocations

    @hybrid_property
    def __related__(self):
        return RawLocation

    def __rawgroup__(self, session, key):
        if key in RawLocation.__dict__:
            return session.query(RawLocation.__dict__[key], func.count()).filter(
                RawLocation.location_id == self.id).group_by(
                    RawLocation.__dict__[key]).all()
        else:
            return []

    def relink(self, session, obj):
        if obj == self:
            return
        if obj.__tablename__[:3] == "raw":
            self.assignees.extend([asg.assignee for asg in obj.rawassignees if asg.assignee])
            self.inventors.extend([inv.inventor for inv in obj.rawinventors if inv.inventor])
            self.rawlocations.append(obj)
        else:
            self.assignees.extend(obj.assignees)
            self.inventors.extend(obj.inventors)
            self.rawlocations.extend(obj.rawlocations)

        self.assignees = list(set(self.assignees))
        self.inventors = list(set(self.inventors))
        self.rawlocations = list(set(self.rawlocations))

    def update(self, **kwargs):
        if "city" in kwargs:
            self.city = kwargs["city"]
        if "state" in kwargs:
            self.state = kwargs["state"]
        if "country" in kwargs:
            self.country = kwargs["country"]
        if "latitude" in kwargs:
            self.latitude = kwargs["latitude"]
        if "longitude" in kwargs:
            self.longitude = kwargs["longitude"]

    # ----------------------------------

    def __repr__(self):
        return "<Location('{0}')>".format(self.address)


# OBJECTS --------------------------


class RawAssignee(Base):
    __tablename__ = "rawassignee"
    uuid = Column(Unicode(36), primary_key=True)
    patent_id = Column(Unicode(20), ForeignKey("patent.id"))
    assignee_id = Column(Unicode(36), ForeignKey("assignee.id"))
    rawlocation_id = Column(Unicode(256), ForeignKey("rawlocation.id"))
    type = Column(Unicode(10))
    name_first = Column(Unicode(64))
    name_last = Column(Unicode(64))
    organization = Column(Unicode(256))
    residence = Column(Unicode(10))
    nationality = Column(Unicode(10))
    sequence = Column(Integer, index=True)

    # -- Functions for Disambiguation --

    @hybrid_property
    def summarize(self):
        return {
            "type": self.type,
            "name_first": self.name_first,
            "name_last": self.name_last,
            "organization": self.organization,
            "residence": self.residence,
            "nationality": self.nationality}

    @hybrid_property
    def __clean__(self):
        return self.assignee

    @hybrid_property
    def __related__(self):
        return Assignee

    def unlink(self, session):
        clean = self.__clean__
        clean.__raw__.pop(clean.__raw__.index(self))
        clean.patents = [obj.patent for obj in clean.__raw__]
        clean.locations = [obj.rawlocation.location for obj in clean.__raw__ if obj.rawlocation.location]
        clean.patents = list(set(clean.patents))
        clean.locations = list(set(clean.locations))

    # ----------------------------------

    def __repr__(self):
        if self.organization:
            return_string = self.organization
        else:
            return_string = u"{0} {1}".format(self.name_first, self.name_last)
        return "<RawAssignee('{0}')>".format(unidecode(return_string))


class RawInventor(Base):
    __tablename__ = "rawinventor"
    uuid = Column(Unicode(36), primary_key=True)
    patent_id = Column(Unicode(20), ForeignKey("patent.id"))
    inventor_id = Column(Unicode(36), ForeignKey("inventor.id"))
    rawlocation_id = Column(Unicode(256), ForeignKey("rawlocation.id"))
    name_first = Column(Unicode(64))
    name_last = Column(Unicode(64))
    nationality = Column(Unicode(10))
    sequence = Column(Integer, index=True)

    # -- Functions for Disambiguation --

    @hybrid_property
    def summarize(self):
        return {
            "name_first": self.name_first,
            "name_last": self.name_last,
            "nationality": self.nationality}

    @hybrid_property
    def __clean__(self):
        return self.inventor

    @hybrid_property
    def __related__(self):
        return Inventor

    def unlink(self, session):
        clean = self.__clean__
        clean.__raw__.pop(clean.__raw__.index(self))
        clean.patents = [obj.patent for obj in clean.__raw__]
        clean.locations = [obj.rawlocation.location for obj in clean.__raw__ if obj.rawlocation.location]
        clean.patents = list(set(clean.patents))
        clean.locations = list(set(clean.locations))

    # ----------------------------------

    @hybrid_property
    def name_full(self):
        return u"{first} {last}".format(
            first=self.name_first,
            last=self.name_last)

    def __repr__(self):
        return "<RawInventor('{0}')>".format(unidecode(self.name_full))


class RawLawyer(Base):
    __tablename__ = "rawlawyer"
    uuid = Column(Unicode(36), primary_key=True)
    lawyer_id = Column(Unicode(36), ForeignKey("lawyer.id"))
    patent_id = Column(Unicode(20), ForeignKey("patent.id"))
    name_first = Column(Unicode(64))
    name_last = Column(Unicode(64))
    organization = Column(Unicode(64))
    country = Column(Unicode(10))
    sequence = Column(Integer, index=True)

    @hybrid_property
    def name_full(self):
        return u"{first} {last}".format(
            first=self.name_first,
            last=self.name_last)

    # -- Functions for Disambiguation --

    @hybrid_property
    def summarize(self):
        return {
            "name_first": self.name_first,
            "name_last": self.name_last,
            "organization": self.organization,
            "country": self.country}

    @hybrid_property
    def __clean__(self):
        return self.lawyer

    @hybrid_property
    def __related__(self):
        return Lawyer

    def unlink(self, session):
        clean = self.__clean__
        clean.__raw__.pop(clean.__raw__.index(self))
        clean.patents = [obj.patent for obj in clean.__raw__]
        clean.patents = list(set(clean.patents))

    # ----------------------------------

    def __repr__(self):
        data = []
        if self.name_first:
            data.append("{0} {1}".format(self.name_first, self.name_last))
        if self.organization:
            data.append(self.organization)
        return "<RawLawyer('{0}')>".format(unidecode(", ".join(data)))


# DISAMBIGUATED -----------------------


class Assignee(Base):
    __tablename__ = "assignee"
    id = Column(Unicode(36), primary_key=True)
    type = Column(Unicode(10))
    name_first = Column(Unicode(64))
    name_last = Column(Unicode(64))
    organization = Column(Unicode(256))
    residence = Column(Unicode(10))
    nationality = Column(Unicode(10))
    rawassignees = relationship("RawAssignee", backref="assignee")

    # -- Functions for Disambiguation --

    @hybrid_property
    def summarize(self):
        return {
            "id": self.id,
            "type": self.type,
            "name_first": self.name_first,
            "name_last": self.name_last,
            "organization": self.organization,
            "residence": self.residence,
            "nationality": self.nationality}

    @hybrid_property
    def __raw__(self):
        return self.rawassignees

    @hybrid_property
    def __related__(self):
        return RawAssignee

    def __rawgroup__(self, session, key):
        if key in RawAssignee.__dict__:
            return session.query(RawAssignee.__dict__[key], func.count()).filter(
                RawAssignee.assignee_id == self.id).group_by(
                    RawAssignee.__dict__[key]).all()
        else:
            return []

    def relink(self, session, obj):
        if obj == self:
            return
        if obj.__tablename__[:3] == "raw":
            if obj.rawlocation.location:
                self.locations.append(obj.rawlocation.location)
            self.patents.append(obj.patent)
            self.rawassignees.append(obj)
        else:
            self.patents.extend(obj.patents)
            self.locations.extend(obj.locations)
            self.rawassignees.extend(obj.rawassignees)

        self.patents = list(set(self.patents))
        self.locations = list(set(self.locations))
        self.rawassignees = list(set(self.rawassignees))

    def update(self, **kwargs):
        if "type" in kwargs:
            self.type = kwargs["type"]
        if "name_first" in kwargs:
            self.name_first = kwargs["name_first"]
        if "name_last" in kwargs:
            self.name_last = kwargs["name_last"]
        if "organization" in kwargs:
            self.organization = kwargs["organization"]
        if "residence" in kwargs:
            self.residence = kwargs["residence"]
        if "nationality" in kwargs:
            self.nationality = kwargs["nationality"]

    # ----------------------------------

    def __repr__(self):
        if self.organization:
            return_string = self.organization
        else:
            return_string = u"{0} {1}".format(self.name_first, self.name_last)
        return "<Assignee('{0}')>".format(unidecode(return_string))


class Inventor(Base):
    __tablename__ = "inventor"
    id = Column(Unicode(36), primary_key=True)
    name_first = Column(Unicode(64))
    name_last = Column(Unicode(64))
    nationality = Column(Unicode(10))
    rawinventors = relationship("RawInventor", backref="inventor")

    @hybrid_property
    def name_full(self):
        return u"{first} {last}".format(
            first=self.name_first,
            last=self.name_last)

    # -- Functions for Disambiguation --

    @hybrid_property
    def summarize(self):
        return {
            "id": self.id,
            "name_first": self.name_first,
            "name_last": self.name_last,
            "nationality": self.nationality}

    @hybrid_property
    def __raw__(self):
        return self.rawinventors

    @hybrid_property
    def __related__(self):
        return RawInventor

    def __rawgroup__(self, session, key):
        if key in RawInventor.__dict__:
            return session.query(RawInventor.__dict__[key], func.count()).filter(
                RawInventor.inventor_id == self.id).group_by(
                    RawInventor.__dict__[key]).all()
        else:
            return []

    def relink(self, session, obj):
        if obj == self:
            return
        if obj.__tablename__[:3] == "raw":
            if obj.rawlocation.location:
                self.locations.append(obj.rawlocation.location)
            self.patents.append(obj.patent)
            self.rawinventors.append(obj)
        else:
            self.patents.extend(obj.patents)
            self.locations.extend(obj.locations)
            self.rawinventors.extend(obj.rawinventors)

        self.patents = list(set(self.patents))
        self.locations = list(set(self.locations))
        self.rawinventors = list(set(self.rawinventors))

        #session.query(RawInventor).filter(
        #    RawInventor.inventor_id == obj.id).update(
        #        {RawInventor.inventor_id: self.id},
        #        synchronize_session=False)
        #session.query(patentinventor).filter(
        #    patentinventor.c.inventor_id == obj.id).update(
        #        {patentinventor.c.inventor_id: self.id},
        #        synchronize_session=False)
        #session.query(locationinventor).filter(
        #    locationinventor.c.inventor_id == obj.id).update(
        #        {locationinventor.c.inventor_id: self.id},
        #        synchronize_session=False)

    def update(self, **kwargs):
        if "name_first" in kwargs:
            self.name_first = kwargs["name_first"]
        if "name_last" in kwargs:
            self.name_last = kwargs["name_last"]
        if "nationality" in kwargs:
            self.nationality = kwargs["nationality"]

    # ----------------------------------

    def __repr__(self):
        return "<Inventor('{0}')>".format(unidecode(self.name_full))


class Lawyer(Base):
    __tablename__ = "lawyer"
    id = Column(Unicode(36), primary_key=True)
    name_first = Column(Unicode(64))
    name_last = Column(Unicode(64))
    organization = Column(Unicode(64))
    country = Column(Unicode(10))
    rawlawyers = relationship("RawLawyer", backref="lawyer")

    @hybrid_property
    def name_full(self):
        return u"{first} {last}".format(
            first=self.name_first,
            last=self.name_last)

    # -- Functions for Disambiguation --

    @hybrid_property
    def summarize(self):
        return {
            "id": self.id,
            "name_first": self.name_first,
            "name_last": self.name_last,
            "organization": self.organization,
            "country": self.country}

    @hybrid_property
    def __raw__(self):
        return self.rawlawyers

    @hybrid_property
    def __related__(self):
        return RawLawyer

    def __rawgroup__(self, session, key):
        if key in RawLawyer.__dict__:
            return session.query(RawLawyer.__dict__[key], func.count()).filter(
                RawLawyer.lawyer_id == self.id).group_by(
                    RawLawyer.__dict__[key]).all()
        else:
            return []

    def relink(self, session, obj):
        if obj == self:
            return
        if obj.__tablename__[:3] == "raw":
            if obj.patent and obj.patent:
                self.patents.append(obj.patent)
            self.rawlawyers.append(obj)
        else:
            self.patents.extend(obj.patents)
            self.rawlawyers.extend(obj.rawlawyers)

        self.patents = list(set(self.patents))
        self.rawlawyers = list(set(self.rawlawyers))

    def update(self, **kwargs):
        if "name_first" in kwargs:
            self.name_first = kwargs["name_first"]
        if "name_last" in kwargs:
            self.name_last = kwargs["name_last"]
        if "organization" in kwargs:
            self.organization = kwargs["organization"]
        if "country" in kwargs:
            self.country = kwargs["country"]

    # ----------------------------------

    def __repr__(self):
        data = []
        if self.name_full:
            data.append(self.name_full)
        if self.organization:
            data.append(self.organization)
        return "<Lawyer('{0}')>".format(unidecode(", ".join(data)))


# CLASSIFICATIONS ------------------


class USPC(Base):
    __tablename__ = "uspc"
    uuid = Column(Unicode(36), primary_key=True)
    patent_id = Column(Unicode(20), ForeignKey("patent.id"))
    mainclass_id = Column(Unicode(10), ForeignKey("mainclass.id"))
    subclass_id = Column(Unicode(10), ForeignKey("subclass.id"))
    sequence = Column(Integer, index=True)

    def __repr__(self):
        return "<USPC('{1}')>".format(self.subclass_id)


class IPCR(Base):
    __tablename__ = "ipcr"
    uuid = Column(Unicode(36), primary_key=True)
    patent_id = Column(Unicode(20), ForeignKey("patent.id"))
    classification_level = Column(Unicode(20))
    section = Column(Unicode(20))
    subclass = Column(Unicode(20))
    main_group = Column(Unicode(20))
    subgroup = Column(Unicode(20))
    symbol_position = Column(Unicode(20))
    classification_value = Column(Unicode(20))
    classification_status = Column(Unicode(20))
    classification_data_source = Column(Unicode(20))
    action_date = Column(Date, index=True)
    ipc_version_indicator = Column(Date, index=True)
    sequence = Column(Integer, index=True)


class MainClass(Base):
    __tablename__ = "mainclass"
    id = Column(Unicode(20), primary_key=True)
    title = Column(Unicode(256))
    text = Column(Unicode(256))
    uspc = relationship("USPC", backref="mainclass")

    def __repr__(self):
        return "<MainClass('{0}')>".format(self.id)


class SubClass(Base):
    __tablename__ = "subclass"
    id = Column(Unicode(20), primary_key=True)
    title = Column(Unicode(256))
    text = Column(Unicode(256))
    uspc = relationship("USPC", backref="subclass")

    def __repr__(self):
        return "<SubClass('{0}')>".format(self.id)


# REFERENCES -----------------------


class Citation(Base):
    """
    Two types of citations?
    """
    __tablename__ = "citation"
    uuid = Column(Unicode(36), primary_key=True)
    patent_id = Column(Unicode(20), ForeignKey("patent.id"))
    citation_id = Column(Unicode(20), ForeignKey("patent.id"))
    date = Column(Date)
    name = Column(Unicode(64))
    kind = Column(Unicode(10))
    number = Column(Unicode(64))
    country = Column(Unicode(10))
    category = Column(Unicode(20))
    sequence = Column(Integer)

    def __repr__(self):
        return "<Citation('{0}, {1}')>".format(self.number, self.date)


class OtherReference(Base):
    __tablename__ = "otherreference"
    uuid = Column(Unicode(36), primary_key=True)
    patent_id = Column(Unicode(20), ForeignKey("patent.id"))
    text = deferred(Column(UnicodeText))
    sequence = Column(Integer)

    def __repr__(self):
        return "<OtherReference('{0}')>".format(unidecode(self.text[:20]))


class USRelDoc(Base):
    __tablename__ = "usreldoc"
    uuid = Column(Unicode(36), primary_key=True)
    patent_id = Column(Unicode(20), ForeignKey("patent.id"))
    rel_id = Column(Unicode(20), ForeignKey("patent.id"))
    doctype = Column(Unicode(64), index=True)
    status = Column(Unicode(20))
    date = Column(Date, index=True)
    number = Column(Unicode(64), index=True)
    kind = Column(Unicode(10))
    country = Column(Unicode(20), index=True)
    relationship = Column(Unicode(64))
    sequence = Column(Integer, index=True)

    def __repr__(self):
        return "<USRelDoc('{0}, {1}')>".format(self.number, self.date)
