from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, DecimalField, SelectField, TextAreaField, BooleanField, PasswordField
from wtforms.validators import InputRequired, Length, URL, NumberRange, ValidationError
from decimal import Decimal
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
        validators=[NumberRange(min=60*10, max=None, message='Cadence must be at least 10 minutes.'), InputRequired()])
    # number of seconds to offset from utc or None
    offset = IntegerField(
        'Offset',
        validators=[NumberRange(min=0, max=86399, message='Offset is in seconds. Is not required.')])
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
        # validators=[URL()] # don't validate as a URL because '' is valid too.
    )
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
    amount = DecimalField(
        'Amount',
        places=8,
        rounding=None,
        validators=[NumberRange(min=Decimal('0.00000001'), max=None, message='You must send at least 1')])
    sweep = BooleanField(
        'Send Everything',
        description='Sends everything in the wallet (including SATORI tokens and currency) to the address specified.',
        default=False,
        validators=[])
    submit = SubmitField('Send')


class VaultPassword(FlaskForm):
    password = PasswordField(
        'Password',
        validators=[InputRequired(), Length(min=8, max=256)])
    submit = SubmitField('Unlock')


class ChatPrompt(FlaskForm):
    prompt = StringField(
        'prompt',
        validators=[InputRequired(), Length(min=8)])
    submit = SubmitField('Ask')


#class CreateProposal(FlaskForm):
    # str
    #...
