# -*- coding: utf-8 -*-

from flask import Flask, abort
from flask import request
from flask import render_template
from flask import session, url_for, redirect, flash
from flask_wtf.csrf import CSRFProtect
from flask import copy_current_request_context
from flask_mail import Mail, Message
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager
from config import DevelopmentConfig
from models import dbm as db, User, Comment, Location, Device
from helpers import date_format
from api import api_blueprint
import threading
import forms

app = Flask(__name__)

#cargo las configuraciones desde la clase
app.config.from_object(DevelopmentConfig)
csrf = CSRFProtect()
csrf.init_app(app)
# Agrego la api mediante blueprint
app.register_blueprint(api_blueprint)
csrf.exempt(api_blueprint)
#para que la db tome las configuraciones
db.init_app(app)
mail = Mail(app)

migrate = Migrate(app, db)
manager = Manager(app)
manager.add_command('db', MigrateCommand)


def send_email(username, email, message, subject):
    """Metodo para la generacion y envio de emails"""
    msg = Message(subject,
        sender=app.config['MAIL_USERNAME'],
        recipients=[email, ])
    msg.add_recipient('helpdesk@dadalogistica.com.ar')
    msg.html = render_template('mail.html', user=username, message=message)
    mail.send(msg)

with app.app_context():
    db.create_all()
    user = User(username='admin', email='admin@example.com',
        password='admin', staff=True)
    try:
        user.add()
    except Exception as e:
        print(e)


@app.errorhandler(404)
def page_not_found(error):
    """Se utiliza para el renderizado de un template personalizado ante un
    response 404"""
    return render_template('404.html'), 404


@app.before_request
def berfore_request():
    """Esta funcion con decorador @app.before_request se ejecuta antes
     de procesar el request"""
    pass


@app.after_request
def after_request(response):
    """Esta funcion se ejecuta posterior al procesamiento del request, por lo
    cual se retorna el objeto response"""
    return response


@app.route('/')
@app.route('/index')
def index():
    """Renderiza el template index y da la bienvenida al usuario"""
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login, por default se carga un usuario admin de password admin"""
    login_form = forms.LoginForm(request.form)
    if request.method == 'POST' and login_form.validate():
        username = login_form.username.data
        password = login_form.password.data
        user = User.query.filter_by(username=username).first()
        if user is not None and user.verify_password(password) and user.staff is True:
            flash(('info', 'Bienvenido {}.'.format(username)))
            session['username'] = username
            session['user_id'] = user.id
            session['urls_u'] = ({'url': 'view_user', 'name': 'View Users'},
                {'url': 'new_user', 'name': 'New User'})
            session['urls_d'] = (
                {'url': 'view_devices', 'name': 'View Devices'},
                {'url': 'new_device', 'name': 'New Device'},
                {'url': 'assign_device', 'name': 'Assign Device'},)
            return redirect(url_for('index'))
        else:
            flash(('danger', 'Contraseña o usuario incorrectos.'))
    return render_template('login.html', form=login_form)


@app.route('/logout')
def logout():
    """User loguot, se realiza un clean del objeto session"""
    if 'username' in session:
        session.clear()
    flash(('info', 'Gracias! Vuelva pronto!'))
    return redirect(url_for('index'))


@app.route('/user/new', methods=['GET', 'POST'])
@app.route('/user/new/<int:id>', methods=['GET', 'POST'])
def new_user(id=None):
    """Agrega y actualiza los el objeto User"""
    if id is not None:
        user = User.query.filter(User.id == id).one_or_none()
        if user is None:
            flash(('danger', 'Lo sentimos algo salio mal!.'))
            return redirect(url_for('view_user'))
        if request.method == 'GET':
            user_form = forms.CreateUserForm(obj=user)
        elif request.method == 'POST':
            user_form = forms.CreateUserForm(request.form)
            user_form.location.choices = [(g.id, g.location_name) for g in Location.query.order_by('location_name').all()]
            user_c = User.query.filter_by(username=user_form.username.data).one_or_none()
            if user_c is not None and user_c.id != id:
                flash(('danger', 'El usuario ya se encuentra registrado!'))
                return render_template('new_user.html', form=user_form)
            if user_form.validate():
                user_form.populate_obj(user)
                try:
                    user.update()
                    flash(('success', 'Usuario creado correctamente.'))
                    return redirect(url_for('new_user'))
                except Exception as e:
                    print(e)
                    flash(('danger', 'Lo sentimos algo salio mal!.'))
                    return redirect(url_for('index'))
    else:
        user_form = forms.CreateUserForm(request.form)
        user_form.location.choices = [(g.id, g.location_name) for g in Location.query.order_by('location_name').all()]
        user = User.query.filter_by(username=user_form.username.data).first()
        if user is not None:
            flash(('danger', 'El usuario ya se encuentra registrado!'))
            return render_template('new_user.html', form=user_form)
        if request.method == 'POST' and user_form.validate():
            user = User(user_form.username.data,
                user_form.email.data,
                user_form.password.data,
                user_form.staff.data, user_form.first_name.data,
                user_form.last_name.data,
                user_form.location.data, user_form.phone.data)
            try:
                user.add()
                flash(('success', 'Usuario creado correctamente.'))
                return redirect(url_for('new_user'))
            except Exception as e:
                print(e)
                flash(('danger', 'Lo sentimos algo salio mal!.'))
                return redirect(url_for('index'))
    user_form.location.choices = [(g.id, g.location_name) for g in Location.query.order_by('location_name').all()]
    return render_template('new_user.html', form=user_form)


@app.route('/user/del/<int:id>')
def del_user(id):
    """Elimina el usuario del id suministrado en la url"""
    user = User.query.filter(User.id == id).one_or_none()
    if user is not None:
        if len(user.device_id) is 0:
            try:
                user.delete()
                flash(('success', 'Usuario borrado exitosamente!.'))
                return redirect(url_for('view_user'))
            except Exception as e:
                print(e)
                flash(('danger', 'Lo sentimos algo salio mal!.'))
                return redirect(url_for('index'))
        else:
            flash(('danger',
            'Para eliminar, se debe quitar los dispositivos asignados!.'))
            return redirect(url_for('view_user', uid=id))
    flash(('danger', 'Lo sentimos algo salio mal!.'))
    return redirect(url_for('view_user'))


@app.route('/user/view', methods=['GET'])
@app.route('/user/view/<int:uid>', methods=['GET'])
def view_user(uid=None):
    """Se renderiza el template de visualizacion de usuarios si uid no es
    suministrado en la url, si se suministra un id valido se renderiza el
    template de detalle de usuario"""
    if uid is None:
        users = User.query.join(Location).add_columns(Location.location_name).order_by(User.username).all()
        return render_template('view_users.html', users=users)
    else:
        try:
            user = User.query.filter(User.id == uid).one()
        except Exception as e:
            print(e)
            flash(('danger', 'Usuario no encontrado!.'))
            return redirect(url_for('index'))
        return render_template('view_user.html', user=user)


@app.route('/device/new', methods=['GET', 'POST'])
@app.route('/device/new/<int:id>', methods=['GET', 'POST'])
def new_device(id=None):
    """Creacion y actualizacion de objetos Device"""
    if id is None:
        form = forms.CreateDevice(request.form)
    else:
        form = forms.UpdateDevice(request.form)
    form.location.choices = [(g.id, g.location_name) for g in Location.query.order_by('location_name').all()]
    if request.method == 'GET' and id is not None:
        dev = Device.query.filter(Device.id == id).one_or_none()
        if dev is not None:
            form.name.data = dev.name
            form.location.data = dev.location
            form.serial_number.data = dev.serial_number
            form.description.data = dev.description
            form.teamviwer.data = dev.teamviwer
            form.type_device.data = dev.type_device
            form.model.data = dev.model
            form.marca.data = dev.marca
            form.system.data = dev.system
        else:
            abort(404)
    if request.method == 'POST' and form.validate():
        if id is not None:
            dev = Device.query.filter(Device.id == id).one()
            form.populate_obj(dev)
        else:
            dev = Device(name=form.name.data,
                serial_number=form.serial_number.data,
                description=form.description.data,
                teamviwer=form.teamviwer.data,
                type_device=form.type_device.data, location=form.location.data,
                marca=form.marca.data, model=form.model.data,
                system=form.system.data)
        try:
            if dev.id is None:
                dev.add()
            else:
                dev.update()
            flash(('success', 'Dispositivo guardado exitosamente!.'))
            return redirect(url_for('new_device'))
        except Exception as e:
            print(e)
            flash(('danger', 'Lo sentimos algo salio mal!.'))
            return redirect(url_for('index'))
    return render_template('new_device.html', form=form)


@app.route('/device/view', methods=['GET'])
@app.route('/device/view/<int:did>', methods=['GET'])
def view_devices(did=None):
    """Visualizacion de todos los objetos Device o del template de detalle del
    dispositivo si es que un id valido es suministrado en la url"""
    if did is None:
        devs = Device.query.order_by(Device.name).outerjoin(Location).add_columns(Location.location_name).all()
        return render_template('view_devices.html', devs=devs)
    else:
        try:
            dev = Device.query.filter(Device.id == did).join(Location).add_columns(Location.location_name).one()
        except Exception as e:
            print(e)
            flash(('danger', 'Dispositivo no encontrado!.'))
            return redirect(url_for('index'))
        form = forms.CommentForm(request.form)
        return render_template('view_device.html', dev=dev, form=form,
            date_format=date_format)


@app.route('/device/del/<int:id>')
def del_device(id):
    """Eliminacion del dispositivo de id suministrado en la url mientras que
    sea valido y exista"""
    dev = Device.query.filter(Device.id == id).one_or_none()
    if dev is not None:
        if dev.user_id is None:
            try:
                dev.delete()
                flash(('success', 'Dispositivo se borro exitosamente!.'))
                return redirect(url_for('view_devices'))
            except Exception as e:
                print(e)
                flash(('danger', 'Lo sentimos algo salio mal!.'))
                return redirect(url_for('index'))
        else:
            flash(('info', 'No es posible eliminar equipos asignados!.'))
            return redirect(url_for('view_devices'))
    flash(('danger', 'Lo sentimos algo salio mal!.'))
    return redirect(url_for('view_devices'))


@app.route('/device/state/<int:did>', methods=['GET'])
def change_device_state(did):
    """Cambia el estado del dispositivo con id suministrado mediante la url,
    dependiendo de en que estado se encuentre"""
    dev = Device.query.filter(Device.id == did).one_or_none()
    if dev is not None:
        try:
            if dev.active:
                dev.active = False
            else:
                dev.active = True
            dev.update()
            flash(('success', 'Estado cambiado exitosamente!.'))
            return redirect(url_for('view_devices', did=dev.id))
        except Exception as e:
            print(e)
            flash(('danger', 'Lo sentimos algo salio mal!.'))
            return redirect(url_for('view_devices', did=dev.id))
    flash(('danger', 'Lo sentimos algo salio mal!.'))
    return redirect(url_for('view_devices', did=dev.id))


@app.route('/device/assign', methods=['GET', 'POST'])
def assign_device():
    """Tratamineto de la asignacion de dispositivos a usuarios"""
    form = forms.AssignDevice(request.form)
    if request.method == 'GET':
        form.device.choices = [(g.id, g.name) for g in Device.query.filter(Device.user_id == None).filter(Device.active).order_by('name').all()]
        if len(form.device.choices) is 0:
            flash(('danger',
            'Lo sentimos no hay equipos disponibles para asignar!.'))
            return redirect(url_for('view_devices'))
        form.user.choices = [(g.id, g.username) for g in User.query.filter(User.username != 'admin').order_by('username').all()]
        return render_template('assign_dev.html', form=form)
    elif request.method == 'POST':
        dev = Device.query.filter(Device.id == form.device.data).one_or_none()
        user = User.query.filter(User.id == form.user.data).one_or_none()
        if (dev and user) is not None:
            dev.user_id = user.id
            try:
                dev.update()
                flash(('success', 'Dispositivo guardado exitosamente!.'))
                username = user.username
                email = user.email
                dname = dev.name
                if form.notify.data:
                    @copy_current_request_context
                    def send_message(username, email, dname):
                        send_email(username, email,
                            'El dispositivo ' + dname + ' le ha sido asignado.',
                            'Asignacion de equipo.')
                    sender = threading.Thread(name='mail_sender',
                        target=send_message, args=(username, email, dname, ))
                    sender.start()
                return redirect(url_for('assign_device'))
            except Exception as e:
                print(e)
                flash(('danger', 'Lo sentimos algo salio mal!.'))
                return redirect(url_for('index'))
        else:
            flash(('danger', 'Lo sentimos algo salio mal!.'))
            return redirect(url_for('assign_device'))


@app.route('/device/unassign/<int:did>', methods=['GET'])
def unassign_device(did):
    """Quita la asignacion del dispositivo con id suministrado en la url"""
    uid = request.args.get('uid', None)
    dev = Device.query.filter(Device.id == did).one_or_none()
    if (dev and uid) is not None:
        dev.user_id = None
        try:
            dev.update()
            flash(('success', 'Dispositivo se borro exitosamente!.'))
            return redirect(url_for('view_user', uid=uid))
        except Exception as e:
            print(e)
            flash(('danger', 'Lo sentimos algo salio mal!.'))
            return redirect(url_for('index'))
    flash(('danger', 'Lo sentimos algo salio mal!.'))
    return redirect(url_for('view_user', uid=uid))


@app.route('/device/<int:did>/comment/add', methods=['POST'])
def add_comment(did):
    """Agrega un comentario a un dispositivo como seguimiento del eventos
    asociados al mismo"""
    form = forms.CommentForm(request.form)
    if request.method == 'POST' and form.validate():
        comment = Comment(session['user_id'], did, form.comment.data)
        try:
            comment.add()
            flash(('success', 'Comentario guardado exitosamente!.'))
            return redirect(url_for('view_devices', did=did))
        except Exception as e:
            print(e)
            flash(('danger', 'Lo sentimos algo salio mal!.'))
            return redirect(url_for('view_devices', did=did))
    flash(('danger', 'Lo sentimos algo salio mal!.'))
    return redirect(url_for('view_devices', did=did))


@app.route('/device/<int:did>/comment/del/<int:cid>', methods=['GET'])
def del_comment(did, cid):
    """Borra un comentario asociado a un dispositivo especifico"""
    cm = Comment.query.filter(Comment.id == cid).one_or_none()
    if cm is not None:
        try:
            cm.delete()
            flash(('success', 'El comentario se borro exitosamente!.'))
            return redirect(url_for('view_devices', did=did))
        except Exception as e:
            print(e)
            flash(('danger', 'Lo sentimos algo salio mal!.'))
            return redirect(url_for('view_devices', did=did))
    flash(('danger', 'Lo sentimos algo salio mal!.'))
    return redirect(url_for('view_devices', did=did))


@app.route('/location/new', methods=['GET', 'POST'])
@app.route('/location/new/<int:id>', methods=['GET', 'POST'])
def new_location(id=None):
    """Agregado y actualizacion de ojetos Location"""
    locations = Location.query.order_by('location_name').all()
    form = forms.CreateLocation(request.form)
    if request.method == 'GET' and id is not None:
        loc = Location.query.filter(Location.id == id).one_or_none()
        if loc is not None:
            form.name.data = loc.location_name
        else:
            abort(404)
    if request.method == 'POST' and form.validate():
        if id is not None:
            loc = Location.query.filter(Location.id == id).one()
            loc.location_name = form.name.data
        else:
            loc = Location(name=form.name.data)
        try:
            if loc.id is None:
                loc.add()
            else:
                loc.update()
            flash(('success', 'Locacion guardado exitosamente!.'))
            return redirect(url_for('new_location'))
        except Exception as e:
            print(e)
            flash(('danger', 'Lo sentimos algo salio mal!.'))
    return render_template('new_location.html', form=form, locations=locations)


@app.route('/location/del/<int:id>')
def del_location(id):
    """Borra un objeto Location"""
    loc = Location.query.filter(Location.id == id).one_or_none()
    if loc is not None:
        try:
            loc.delete()
            flash(('success', 'Locacion se borro exitosamente!.'))
            return redirect(url_for('new_location'))
        except Exception as e:
            print(e)
            flash(('danger', 'Lo sentimos algo salio mal!.'))
    return redirect(url_for('new_location'))