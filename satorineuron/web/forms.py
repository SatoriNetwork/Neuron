from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, SelectField, TextAreaField
from wtforms.validators import InputRequired, Length, URL, NumberRange, ValidationError
from satorineuron import config


class EditConfigurationForm(FlaskForm):
    flaskPort = IntegerField(config.verbose('flaskPort'), validators=[])
    nodejsPort = IntegerField(config.verbose('nodejsPort'), validators=[])
    dataPath = StringField(config.verbose('dataPath'), validators=[])
    modelPath = StringField(config.verbose('modelPath'), validators=[])
    walletPath = StringField(config.verbose('wallletPath'), validators=[])
    defaultSource = SelectField(config.verbose(
        'defaultSource'), validators=[], choices=['streamr', 'satori'])
    # todo: make this two fields: a list where you can select and remove (can't remove the last one), and you can add by typing in the name on a textfield...
    electrumxServers = SelectField(config.verbose('electrumxServers'), validators=[
    ], choices=[config.electrumxServers()])
    submit = SubmitField('Save')


class RelayStreamForm(FlaskForm):
    # the unique id of the stream - not shown on UI
    topic = TextAreaField(
        'Topic',
        validators=[])
    # str
    name = StringField(
        'Name',
        validators=[InputRequired(), Length(min=3, max=127)])
    # str or None
    target = StringField(
        'Target',
        validators=[Length(min=0, max=127)])
    # number of seconds between api hits, not None
    cadence = IntegerField(
        'Cadence',
        validators=[NumberRange(min=60, max=None, message='Cadence must be at least 60 seconds.'), InputRequired()])
    # number of seconds to offset from utc or None
    offset = IntegerField(
        'Offset',
        validators=[NumberRange(min=1, max=None, message='Offset is in seconds. Is not required.')])
    # type of data, just a str right now, whatever
    datatype = StringField(
        'Datatype',
        validators=[Length(min=0, max=100)])
    # str, not exceeding 1000 chars
    description = TextAreaField(
        'Description',
        validators=[Length(min=0, max=1000)])
    # comma separated string list, each element trimmed
    tags = StringField(
        'Tags',
        validators=[Length(min=0, max=200)])
    # location of API
    url = StringField(
        'Url',
        validators=[URL(), InputRequired()])
    # location of API + details or credentials like API key
    uri = StringField(
        'Uri',
        validators=[URL()])
    # headers for API call
    headers = TextAreaField(
        'Headers',
        validators=[Length(min=0, max=1000)])
    # payload for API call
    payload = TextAreaField(
        'Payload',
        validators=[Length(min=0, max=1000)])
    # python script of a certain structure (a named method with specific inputs)
    hook = TextAreaField(
        'Hook',
        validators=[])
    # python script of a certain structure (a named method with specific inputs)
    history = TextAreaField(
        'History',
        validators=[])
    submit = SubmitField('Save')


class SendSatoriTransaction(FlaskForm):
    # str
    address = StringField(
        'Address',
        validators=[InputRequired(), Length(min=34, max=34)])
    # number of seconds between api hits, not None
    amount = IntegerField(
        'Amount',
        validators=[InputRequired(), NumberRange(min=1, max=None, message='You must send at least 1')])
    submit = SubmitField('Send')
