from sqlalchemy import func
from sqlalchemy import Column, Date, Integer, Float, Boolean
from sqlalchemy import ForeignKey, Index
from sqlalchemy import Unicode, UnicodeText
from sqlalchemy.orm import deferred, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.declarative import declarative_base
from unidecode import unidecode

from sqlalchemy import Table
import schema_func

Base = declarative_base()
cascade = "all, delete, delete-orphan"


def init(self, *args, **kwargs):
    for i, arg in enumerate(args):
        self.__dict__[self.kw[i]] = arg
    for k, v in kwargs.iteritems():
        self.__dict__[k] = v

Base.__init__ = init

# ASSOCIATION ----------------------

applicationassignee = Table(
    'patent_assignee', Base.metadata,
    Column('patent_id', Unicode(20), ForeignKey('patent.id')),
    Column('assignee_id', Unicode(36), ForeignKey('assignee.id')))

applicationinventor = Table(
    'patent_inventor', Base.metadata,
    Column('patent_id', Unicode(20), ForeignKey('patent.id')),
    Column('inventor_id', Unicode(36), ForeignKey('inventor.id')))

applicationlawyer = Table(
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

class Application(Base):
    __tablename__ = "application"
    id = Column(Unicode(36), primary_key=True)
    type = Column(Unicode(20))
    number = Column(Unicode(64))
    country = Column(Unicode(20))
    date = Column(Date)
    abstract = deferred(Column(UnicodeText))
    title = deferred(Column(UnicodeText))
    granted = Column(Boolean)
    num_claims = Column(Integer)
    usapplicationcitations = relationship(
        "USApplicationCitation",
        primaryjoin="Application.id == USApplicationCitation.application_id",
        foreign_keys="USApplicationCitation.application_id",
        backref="application", cascade=cascade)
    __table_args__ = (
        Index("app_idx1", "type", "number"),
        Index("app_idx2", "date"),
    )

    classes = relationship("USPC", backref="application", cascade=cascade)
    ipcrs = relationship("IPCR", backref="application", cascade=cascade)

    rawassignees = relationship("RawAssignee", backref="application", cascade=cascade)
    rawinventors = relationship("RawInventor", backref="application", cascade=cascade)
    rawlawyers = relationship("RawLawyer", backref="application", cascade=cascade)
    claims = relationship("Claim", backref="application", cascade=cascade)
    uspatentcitations = relationship(
        "USPatentCitation",
        primaryjoin="Patent.id == USPatentCitation.application_id",
        backref="application", cascade=cascade)
    uspatentcitedby = relationship(
        "USPatentCitation",
        primaryjoin="Patent.id == USPatentCitation.citation_id",
        foreign_keys="USPatentCitation.citation_id",
        backref="citation", cascade=cascade)
    usapplicationcitations = relationship("USApplicationCitation", backref="application", cascade=cascade)
    foreigncitations = relationship("ForeignCitation", backref="application", cascade=cascade)
    otherreferences = relationship("OtherReference", backref="application", cascade=cascade)
    usreldocs = relationship(
        "USRelDoc",
        primaryjoin="Application.id == USRelDoc.application_id",
        backref="application", cascade=cascade)
    relpatents = relationship(
        "USRelDoc",
        primaryjoin="Application.id == USRelDoc.rel_id",
        foreign_keys="USRelDoc.rel_id",
        backref="relpatent", cascade=cascade)
    assignees = relationship("Assignee", secondary=applicationassignee, backref="applications")
    inventors = relationship("Inventor", secondary=applicationinventor, backref="applications")
    lawyers = relationship("Lawyer", secondary=applicationlawyer, backref="applications")

    __table_args__ = (
        Index("pat_idx1", "type", "number", unique=True),
        Index("pat_idx2", "date"),
    )

    def __repr__(self):
        return "<Application('{0}')>".format(self.id)

    @hybrid_property
    def citations(self):
        return self.uspatentcitations + self.usapplicationcitations +\
                self.foreigncitations + self.otherreferences

    def stats(self):
        return {
            "classes": len(self.classes),
            "ipcrs": len(self.ipcrs),
            "rawassignees": len(self.rawassignees),
            "rawinventors": len(self.rawinventors),
            "rawlawyers": len(self.rawlawyers),
            "otherreferences": len(self.otherreferences),
            "uspatentcitations": len(self.uspatentcitations),
            "usapplicationcitations": len(self.usapplicationcitations),
            "foreigncitations": len(self.foreigncitations),
            "uspatentcitedby": len(self.uspatentcitedby),
            "usreldocs": len(self.usreldocs),
            "relpatents": len(self.relpatents),
        }

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
        # TODO: probably need to rebuild this
        # hrm (see others for examples)
        clean = self.__clean__
        clean.__raw__.pop(clean.__raw__.index(self))
        clean.assignees = []
        clean.inventors = []
        for raw in clean.__raw__:
            for obj in raw.rawassignees:
                if obj.assignee and obj.assignee not in clean.assignees:
                    clean.assignees.append(obj.assignee)
            for obj in raw.rawinventors:
                if obj.inventor and obj.inventor not in clean.inventors:
                    clean.inventors.append(obj.inventor)
        if len(clean.__raw__) == 0:
            session.delete(clean)

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
            if obj and obj not in self.__raw__:
                self.__raw__.append(obj)
            self.assignees = list(set(self.assignees))
            self.inventors = list(set(self.inventors))
        else:
            session.query(RawLocation).filter(
                RawLocation.location_id == obj.id).update(
                    {RawLocation.location_id: self.id},
                    synchronize_session=False)
            session.query(locationassignee).filter(
                locationassignee.c.location_id == obj.id).update(
                    {locationassignee.c.location_id: self.id},
                    synchronize_session=False)
            session.query(locationinventor).filter(
                locationinventor.c.location_id == obj.id).update(
                    {locationinventor.c.location_id: self.id},
                    synchronize_session=False)

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

    @classmethod
    def fetch(self, session, default={}):
        return schema_func.fetch(
            Location,
            [["id"],
             ["city", "state", "country"],
             ["longitude", "latitude"]],
            session, default)

    # ----------------------------------

    def __repr__(self):
        return "<Location('{0}')>".format(self.address)


# OBJECTS --------------------------


class RawAssignee(Base):
    __tablename__ = "rawassignee"
    uuid = Column(Unicode(36), primary_key=True)
    application_id = Column(Unicode(20), ForeignKey("application.id"))
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
        pats = [obj.application_id for obj in clean.__raw__ if obj.application_id == self.application_id]
        locs = [obj.rawlocation.location_id for obj in clean.__raw__ if obj.rawlocation.location_id == self.rawlocation.location_id]
        if len(pats) == 1:
            session.query(applicationassignee).filter(
                applicationassignee.c.application_id == self.application_id).delete(
                    synchronize_session=False)
        if len(locs) == 1:
            session.query(locationassignee).filter(
                locationassignee.c.location_id == self.rawlocation.location_id).delete(
                    synchronize_session=False)
        session.query(RawAssignee).filter(
            RawAssignee.uuid == self.uuid).update(
                {RawAssignee.assignee_id: None},
                synchronize_session=False)
        if len(clean.__raw__) == 0:
            session.delete(clean)
        session.commit()

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
    application_id = Column(Unicode(20), ForeignKey("application.id"))
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
        pats = [obj.application_id for obj in clean.__raw__ if obj.application_id == self.application_id]
        locs = [obj.rawlocation.location_id for obj in clean.__raw__ if obj.rawlocation.location_id == self.rawlocation.location_id]
        if len(pats) == 1:
            session.query(applicationinventor).filter(
                applicationinventor.c.application_id == self.application_id).delete(
                    synchronize_session=False)
        if len(locs) == 1:
            session.query(locationinventor).filter(
                locationinventor.c.location_id == self.rawlocation.location_id).delete(
                    synchronize_session=False)
        session.query(RawInventor).filter(
            RawInventor.uuid == self.uuid).update(
                {RawInventor.inventor_id: None},
                synchronize_session=False)
        if len(clean.__raw__) == 0:
            session.delete(clean)
        session.commit()

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
    application_id = Column(Unicode(20), ForeignKey("application.id"))
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
        pats = [obj.application_id for obj in clean.__raw__ if obj.application_id == self.application_id]
        if len(pats) == 1:
            session.query(applicationlawyer).filter(
                applicationlawyer.c.application_id == self.application_id).delete(
                    synchronize_session=False)
        session.query(RawLawyer).filter(
            RawLawyer.uuid == self.uuid).update(
                {RawLawyer.lawyer_id: None},
                synchronize_session=False)
        if len(clean.__raw__) == 0:
            session.delete(clean)
        session.commit()

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
            if obj.application and obj.application not in self.applications:
                self.applications.append(obj.application)
            if obj and obj not in self.__raw__:
                self.__raw__.append(obj)
        else:
            session.query(RawAssignee).filter(
                RawAssignee.assignee_id == obj.id).update(
                    {RawAssignee.assignee_id: self.id},
                    synchronize_session=False)
            session.query(applicationassignee).filter(
                applicationassignee.c.assignee_id == obj.id).update(
                    {applicationassignee.c.assignee_id: self.id},
                    synchronize_session=False)
            session.query(locationassignee).filter(
                locationassignee.c.assignee_id == obj.id).update(
                    {locationassignee.c.assignee_id: self.id},
                    synchronize_session=False)

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

    @classmethod
    def fetch(self, session, default={}):
        return schema_func.fetch(
            Assignee,
            [["id"]],
            session, default)

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
            if obj.application and obj.application not in self.applications:
                self.applications.append(obj.application)
            if obj and obj not in self.__raw__:
                self.__raw__.append(obj)
        else:
            session.query(RawInventor).filter(
                RawInventor.inventor_id == obj.id).update(
                    {RawInventor.inventor_id: self.id},
                    synchronize_session=False)
            session.query(applicationinventor).filter(
                applicationinventor.c.inventor_id == obj.id).update(
                    {applicationinventor.c.inventor_id: self.id},
                    synchronize_session=False)
            session.query(locationinventor).filter(
                locationinventor.c.inventor_id == obj.id).update(
                    {locationinventor.c.inventor_id: self.id},
                    synchronize_session=False)

    def update(self, **kwargs):
        if "name_first" in kwargs:
            self.name_first = kwargs["name_first"]
        if "name_last" in kwargs:
            self.name_last = kwargs["name_last"]
        if "nationality" in kwargs:
            self.nationality = kwargs["nationality"]

    @classmethod
    def fetch(self, session, default={}):
        return schema_func.fetch(
            Inventor,
            [["id"]],
            session, default)

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
            if obj.application and obj.application not in self.applications:
                self.applications.append(obj.application)
            if obj and obj not in self.__raw__:
                self.__raw__.append(obj)
        else:
            session.query(RawLawyer).filter(
                RawLawyer.lawyer_id == obj.id).update(
                    {RawLawyer.lawyer_id: self.id},
                    synchronize_session=False)
            session.query(applicationlawyer).filter(
                applicationlawyer.c.lawyer_id == obj.id).update(
                    {applicationlawyer.c.lawyer_id: self.id},
                    synchronize_session=False)

    def update(self, **kwargs):
        if "name_first" in kwargs:
            self.name_first = kwargs["name_first"]
        if "name_last" in kwargs:
            self.name_last = kwargs["name_last"]
        if "organization" in kwargs:
            self.organization = kwargs["organization"]
        if "country" in kwargs:
            self.country = kwargs["country"]

    @classmethod
    def fetch(self, session, default={}):
        return schema_func.fetch(
            Lawyer,
            [["id"],
             ["organization"],
             ["name_first", "name_last"]],
            session, default)

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
    application_id = Column(Unicode(20), ForeignKey("application.id"))
    mainclass_id = Column(Unicode(10), ForeignKey("mainclass.id"))
    subclass_id = Column(Unicode(10), ForeignKey("subclass.id"))
    sequence = Column(Integer, index=True)

    def __repr__(self):
        return "<USPC('{1}')>".format(self.subclass_id)


class IPCR(Base):
    __tablename__ = "ipcr"
    uuid = Column(Unicode(36), primary_key=True)
    application_id = Column(Unicode(20), ForeignKey("application.id"))
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

class USapplicationCitation(Base):
    """
    US application Citation schema
    """
    __tablename__ = "usapplicationcitation"
    uuid = Column(Unicode(36), primary_key=True)
    application_id = Column(Unicode(20), ForeignKey("application.id"))
    citation_id = Column(Unicode(20), index=True)
    date = Column(Date)
    name = Column(Unicode(64))
    kind = Column(Unicode(10))
    number = Column(Unicode(64))
    country = Column(Unicode(10))
    category = Column(Unicode(20))
    sequence = Column(Integer)

    def __repr__(self):
        return "<USapplicationCitation('{0} {1}, {2}')>".format(self.application_id, self.citation_id, self.date)

class USApplicationCitation(Base):
    """
    US Application Citation schema
    """
    __tablename__ = "usapplicationcitation"
    uuid = Column(Unicode(36), primary_key=True)
    application_id = Column(Unicode(20), ForeignKey("application.id"))
    application_id = Column(Unicode(20), index=True)
    date = Column(Date)
    name = Column(Unicode(64))
    kind = Column(Unicode(10))
    number = Column(Unicode(64))
    country = Column(Unicode(10))
    category = Column(Unicode(20))
    sequence = Column(Integer)

    def __repr__(self):
        return "<USApplicationCitation('{0} {1}, {2}')>".format(self.application_id, self.application_id, self.date)

class ForeignCitation(Base):
    """
    Foreign Citation schema
    """
    __tablename__ = "foreigncitation"
    uuid = Column(Unicode(36), primary_key=True)
    application_id = Column(Unicode(20), ForeignKey("application.id"))
    date = Column(Date)
    name = Column(Unicode(64))
    kind = Column(Unicode(10))
    number = Column(Unicode(64))
    country = Column(Unicode(10))
    category = Column(Unicode(20))
    sequence = Column(Integer)

    def __repr__(self):
        return "<ForeignCitation('{0} {1}, {2}')>".format(self.application_id, self.number, self.date)


class OtherReference(Base):
    __tablename__ = "otherreference"
    uuid = Column(Unicode(36), primary_key=True)
    application_id = Column(Unicode(20), ForeignKey("application.id"))
    text = deferred(Column(UnicodeText))
    sequence = Column(Integer)

    def __repr__(self):
        return "<OtherReference('{0}')>".format(unidecode(self.text[:20]))


class USRelDoc(Base):
    __tablename__ = "usreldoc"
    uuid = Column(Unicode(36), primary_key=True)
    application_id = Column(Unicode(20), ForeignKey("application.id"))
    rel_id = Column(Unicode(20), index=True)
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

class Claim(Base):
    __tablename__ = "claim"
    uuid = Column(Unicode(36), primary_key=True)
    application_id = Column(Unicode(20), ForeignKey('application.id'))
    text = deferred(Column(UnicodeText))
    dependent = Column(Integer) # if -1, independent
    sequence = Column(Integer, index=True)

    def __repr__(self):
        return "<Claim('{0}')>".format(self.text)

class FutureCitationRank(Base):
    """
    This table contains the rank of each patent by number of future citations
    in each year.  A row in this table will read something like "Patent Number
    X got Y future citations in year Z. It was the Nth most cited application that
    year"
    """
    __tablename__ = "futurecitationrank"
    uuid = Column(Unicode(36), primary_key=True)
    application_id = Column(Unicode(20), ForeignKey('application.id'))
    num_citations = Column(Integer)
    year = Column(Integer)
    rank = Column(Integer)

class InventorRank(Base):
    """
    This table contains the rank of each inventor by how many applications they
    have been granted in a given year.
    """
    __tablename__ = "inventorrank"
    uuid = Column(Unicode(36), primary_key=True)
    inventor_id = Column(Unicode(36), ForeignKey('inventor.id'))
    num_applications = Column(Integer)
    year = Column(Integer)
    rank = Column(Integer)

class CitedBy(Base):
    """
    Table contains direct mapping of application_id to all citation_ids that cite that application.
    Takes place of the much slower foreign key relation in the application table
    """
    __tablename__ = "citedby"
    uuid = Column(Unicode(36), primary_key=True)
    application_id = Column(Unicode(20))
    citation_id = Column(Unicode(36))
    year = Column(Integer)
