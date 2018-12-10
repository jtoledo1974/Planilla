# -*- coding: utf-8 -*-
import os
from pickle import loads
from pprint import pformat
from time import localtime, asctime, sleep
from datetime import datetime

from kivy.config import Config
from kivy.logger import Logger

from jnius import autoclass, cast
from plyer.platforms.android import activity
String = autoclass('java.lang.String')
Context = autoclass('android.content.Context')
Intent = autoclass('android.content.Intent')
PendingIntent = autoclass('android.app.PendingIntent')
PowerManager = autoclass('android.os.PowerManager')
Drawable = autoclass("{}.R$drawable".format(activity.getPackageName()))
NotificationBuilder = autoclass(
    'android.support.v4.app.NotificationCompat$Builder')
PRIORITY_MIN = autoclass(
    'android.support.v4.app.NotificationCompat').PRIORITY_MIN

APP = 'SERVICIO'
alarmas = []
broadcast_receiver = None
pending_alarm = False


def notify(title='', message='', id=0, timeout=10,
           priority=None, defaults=False):

    icon = getattr(Drawable, 'icon')
    noti = NotificationBuilder(activity)
    if defaults:
        noti.setDefaults(autoclass('android.app.Notification').DEFAULT_ALL)
    noti.setContentTitle(String(title.encode('utf-8')))
    noti.setContentText(String(message.encode('utf-8')))
    noti.setSmallIcon(icon)
    noti.setAutoCancel(True)

    if priority is not None:
        noti.setPriority(priority)

    intent = activity.getPackageManager().getLaunchIntentForPackage(
        'org.jtc.planilla')
    noti.setContentIntent(PendingIntent.getActivity(activity, 0, intent, 0))

    activity.getSystemService(Context.NOTIFICATION_SERVICE).notify(
        id, noti.build())


def tdformat(td):
    (hours, seconds) = divmod(td.seconds, 3600)
    (minutes, seconds) = divmod(seconds, 60)
    if hours > 0:
        res = "%dh%dm" % (hours, minutes)
    elif minutes > 3:
        res = "%dm" % minutes
    else:
        res = "%dm%d" % (minutes, seconds)
    return res


def update_notification():
    p = pasadas[0]
    title = "en %s %s %s" % (
        tdformat(p['inicio'] - now),
        'Libre' if p['task'] == 'Libre' else p['task'][:4],
        p['sector'])
    message = tdformat(p['final'] - p['inicio'])

    # Darle una id diferente de la por defecto para actualizar siempre la misma
    # y diferente de si ponemos otra notificación
    notify(title=title, message=message, id=1, priority=PRIORITY_MIN)


def wake_app():
    Logger.info("%s: wake_app %s" % (APP, datetime.now()))

    wl.acquire()
    intent = activity.getPackageManager().getLaunchIntentForPackage(
        'org.jtc.planilla')
    Logger.debug("%s: Starting %s %s" % (APP, intent.toString(),
                                         datetime.now()))
    activity.startActivity(intent)


def sound_alarm(id=-1):
    Logger.info("%s: sound_alarm %s %s" % (APP, id, datetime.now()))

    intent = Intent('org.jtc.planilla.ACTION_ALARM').putExtra(
        "id", id).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    Logger.debug("%s: Starting %s %s" % (APP, intent.toString(),
                                         datetime.now()))
    activity.startActivity(intent)
    global pending_alarm
    pending_alarm = False
    sleep(5)
    wl.release()


def process_broadcast(context, intent):
    Logger.debug("%s: process_broadcast %s %s" % (
        APP, intent.toString(), datetime.now()))

    if intent.getAction() == Intent.ACTION_USER_PRESENT:
        Logger.debug("%s: ACTION_USER_PRESENT %s" % (APP, datetime.now()))
        update_notification()
        return

    elif intent.getAction() == ('org.jtc.planilla.SERVICEALARM'):
        id = intent.getExtras().get('id')
        global pending_alarm
        pending_alarm = id
        wake_app()
        return

    elif intent.getAction() == ('org.jtc.planilla.APP_AWAKE'):
        if pending_alarm:
            sound_alarm(id=pending_alarm)


def schedule_alarms(alarmas):

    Logger.debug("%s: schedule_alarms %s" % (APP, datetime.now()))

    from jnius import autoclass
    from android.broadcast import BroadcastReceiver

    SystemClock = autoclass('android.os.SystemClock')
    AlarmManager = autoclass('android.app.AlarmManager')

    global broadcast_receiver
    broadcast_receiver = BroadcastReceiver(
        process_broadcast,
        ['org.jtc.planilla.SERVICEALARM', Intent.ACTION_USER_PRESENT,
         'org.jtc.planilla.APP_AWAKE'])
    broadcast_receiver.start()

    am = activity.getSystemService(Context.ALARM_SERVICE)

    # Cancelar todas las posibles alarmas que hubiera de un servicio anterior
    intent = Intent(String('org.jtc.planilla.SERVICEALARM'))
    for i in range(20):  # Suponemos que no hay más de 20 alarmas!
        pi = PendingIntent.getBroadcast(activity, i, intent, 0)
        am.cancel(pi)

    # Fijar las nuevas alarmas
    i = 0
    now = datetime.now()
    for id, alarma in alarmas.items():
        intent = Intent(String('org.jtc.planilla.SERVICEALARM')).putExtra(
            "id", id)
        pi = PendingIntent.getBroadcast(
            activity, i, intent, PendingIntent.FLAG_UPDATE_CURRENT)
        ms = (alarma['hora'] - now).seconds * 1000
        Logger.debug("%s: Hora: %s - En %s" % (
            APP, alarma['hora'], tdformat(alarma['hora'] - now)))
        am.set(AlarmManager.ELAPSED_REALTIME_WAKEUP,
               SystemClock.elapsedRealtime() + ms, pi)
        i += 1


def seconds_to_update():
    if not len(pasadas):
        return 60

    t = pasadas[0]['inicio']
    (hours, seconds) = divmod((t - now).seconds, 3600)
    (minutes, seconds) = divmod(seconds, 60)

    if hours < 1 and minutes < 3:
        return 1
    else:
        s = 59 - datetime.now().second
        return s if s else 60


if __name__ == '__main__':

    # Por defecto se arranca foreground. Lo dejamos para que se no muera el
    # servicio activity.stopForeground(False)
    Logger.info("%s: service.__main__ %s" % (APP, datetime.now()))

    arg = loads(eval(os.getenv('PYTHON_SERVICE_ARGUMENT')))
    Logger.debug("%s: PYTHON_SERVICE_ARGUMENT %s" % (APP, pformat(arg)))

    pasadas = arg['pasadas']
    alarmas = arg['alarmas']
    Config.set('kivy', 'log_level', arg['log_level'])

    Logger.debug("%s: Adquiriendo el PowerManager %s" % (APP, datetime.now()))
    pm = activity.getSystemService(Context.POWER_SERVICE)

    # No entiendo por qué no funciona con las tres primeras opciones
    # El uso de FULL_WAKE_LOCK y SCREEN BRIGHT es deprecated
    # pero si no no me rula.
    Logger.debug("%s: Adquiriendo el wake lock %s" % (APP, datetime.now()))
    wl = pm.newWakeLock(
        # PowerManager.PARTIAL_WAKE_LOCK |
        PowerManager.ACQUIRE_CAUSES_WAKEUP |
        PowerManager.ON_AFTER_RELEASE |
        PowerManager.FULL_WAKE_LOCK |
        PowerManager.SCREEN_BRIGHT_WAKE_LOCK |
        0, "My tag")

    schedule_alarms(alarmas)
    if len(alarmas):
        # Humm, no es correcto. No está garantizado que la siguiente clave
        # sea la siguiente alarma.
        Logger.info("%s: Proxima alarma %s" % (
            APP, alarmas[next(iter(alarmas))]))
    while True:
        now = datetime.now()
        Logger.debug("%s: %s" % (APP, asctime(localtime())))

        pasadas = [p for p in pasadas if p['inicio'] > now]
        if not len(pasadas):
            Logger.info("No quedan pasadas. Paramos el servicio")
            # notify(title='Parando el servicio', message='no quedan pasadas',
            #        id=0,
            #        priority=autoclass('android.app.Notification').PRIORITY_MIN)
            activity.stopSelf()
            break

        update_notification()

        sleep(seconds_to_update())
