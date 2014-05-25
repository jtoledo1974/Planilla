# -*- coding: utf-8 -*-
import os
import pickle
from pprint import pformat
from time import localtime, asctime, sleep
from datetime import datetime, timedelta

from kivy.logger import Logger

from jnius import autoclass, cast
from plyer.platforms.android import activity
String = autoclass('java.lang.String')
Context = autoclass('android.content.Context')
Intent = autoclass('android.content.Intent')
PowerManager = autoclass('android.os.PowerManager')
PRIORITY_MIN = autoclass('android.app.Notification').PRIORITY_MIN

import sys
sys.path = ['..']+sys.path
from myandroid import notification

APP = 'SERVICIO'
alarmas = []
broadcast_receiver = None


def tdformat(td):
    (hours, seconds) = divmod(td.seconds, 3600)
    (minutes, seconds) = divmod(seconds, 60)
    if hours > 0:
        res = "%dh%d" % (hours, minutes)
    else:
        res = "%dm" % minutes
    return res


def update_notification():
    p = pasadas[0]
    title = "en %s %s %s" % (
        tdformat(p['inicio']-now),
        'Libre' if p['task'] == 'Libre' else p['task'][:4],
        p['sector'])
    message = tdformat(p['final']-p['inicio'])

    # Darle una id diferente de la por defecto para actualizar siempre la misma
    # y diferente de si ponemos otra notificación
    notification.notify(
        title=title, message=message, icon='icon',
        id=1, priority=PRIORITY_MIN, from_service=True)


def sound_alarm(context=None, intent=None, texto="default"):
    if intent:
        if intent.getAction() == Intent.ACTION_USER_PRESENT:
            Logger.debug("%s: ACTION_USER_PRESENT %s" % (APP, datetime.now()))
            update_notification()
            return
        texto = intent.getExtras().getString('texto')
    Logger.info("%s: %s Sonando alarma %s" % (APP, datetime.now(), texto))

    # Misterios del python for android, sin el cast no funciona
    android_activity = cast('android.app.Activity', activity)
    pm = android_activity.getSystemService(Context.POWER_SERVICE)

    # No entiendo por qué no funciona con las tres primeras opciones
    # El uso de FULL_WAKE_LOCK y SCREEN BRIGHT es deprecated
    # pero si no no me rula.
    wl = pm.newWakeLock(
        # PowerManager.PARTIAL_WAKE_LOCK |
        PowerManager.ACQUIRE_CAUSES_WAKEUP |
        PowerManager.ON_AFTER_RELEASE |
        PowerManager.FULL_WAKE_LOCK |
        PowerManager.SCREEN_BRIGHT_WAKE_LOCK |
        0, "My tag")
    wl.acquire()

    intent = activity.getPackageManager().getLaunchIntentForPackage(
        'org.jtc.planilla').putExtra("texto", String(texto))
    Logger.debug("%s: Starting %s" % (APP, intent.toString()))
    activity.startActivity(intent)

    sleep(7)      # Vamos a asegurarnos de que la aplicación arranca bien,
    wl.release()  # pero menos de 10s o Android nos mata


def calculate_alarms():
    global alarmas
    prev_task = ''
    prev_sector = ''
    for p in pasadas:
        if p['task'] == 'Ejecutivo':
            alarmas.append({
                'hora': p['inicio']-timedelta(minutes=margen_ejec),
                'texto': p['task']+' '+p['sector']})
        elif p['task'] == 'Ayudante':
            alarmas.append({
                'hora': p['inicio']-timedelta(minutes=margen_ayud),
                'texto': p['task']+' '+p['sector']})
        elif p['task'] == 'Libre' and prev_task == 'Ayudante':
            alarmas.append({
                'hora': p['inicio']-timedelta(minutes=margen_ayud),
                'texto': "Quitar tarjeta sector %s" % prev_sector})
        prev_task = p['task']
        prev_sector = p['sector']

    alarmas = [a for a in alarmas if a['hora'] > datetime.now()]
    Logger.info("%s: %s" % (APP, pformat(alarmas)))

    from jnius import autoclass
    from android.broadcast import BroadcastReceiver

    Context = autoclass('android.content.Context')
    Intent = autoclass('android.content.Intent')
    PendingIntent = autoclass('android.app.PendingIntent')
    SystemClock = autoclass('android.os.SystemClock')
    AlarmManager = autoclass('android.app.AlarmManager')

    global broadcast_receiver
    broadcast_receiver = BroadcastReceiver(
        sound_alarm,
        ['org.jtc.planilla.SERVICEALARM', Intent.ACTION_USER_PRESENT])
    broadcast_receiver.context = activity
    broadcast_receiver.start()

    am = activity.getSystemService(Context.ALARM_SERVICE)

    # Cancelar todas las posibles alarmas que hubiera de un servicio anterior
    intent = Intent(String('org.jtc.planilla.SERVICEALARM'))
    for i in range(20):  # Suponemos que no hay más de 20 alarmas!
        pi = PendingIntent.getBroadcast(activity, i, intent, 0)
        am.cancel(pi)

    if False:
        for i in range(10):
            intent = Intent(String('org.jtc.planilla.SERVICEALARM')).putExtra(
                "texto", String("Alarma n. %s" % str(i)))
            pi = PendingIntent.getBroadcast(
                activity, i, intent, PendingIntent.FLAG_UPDATE_CURRENT)
            ms = 10 * i * 1000
            am.set(AlarmManager.ELAPSED_REALTIME_WAKEUP,
                   SystemClock.elapsedRealtime()+ms, pi)
        return
    # Fijar las nuevas alarmas
    i = 0
    now = datetime.now()
    for alarma in alarmas:
        intent = Intent(String('org.jtc.planilla.SERVICEALARM')).putExtra(
            "texto", String(alarma['texto']))
        pi = PendingIntent.getBroadcast(
            activity, i, intent, PendingIntent.FLAG_UPDATE_CURRENT)
        ms = (alarma['hora']-now).seconds * 1000
        Logger.debug("Hora: %s - En %s" % (
            alarma['hora'], tdformat(alarma['hora']-now)))
        am.set(AlarmManager.ELAPSED_REALTIME_WAKEUP,
               SystemClock.elapsedRealtime()+ms, pi)
        i += 1

if __name__ == '__main__':

    # Por defecto se arranca foreground. Lo dejamos para que se no muera el
    # servicio activity.stopForeground(False)

    arg = pickle.loads(os.getenv('PYTHON_SERVICE_ARGUMENT'))
    Logger.debug("%s: PYTHON_SERVICE_ARGUMENT %s" % (APP, pformat(arg)))

    pasadas = arg['pasadas']
    margen_ejec = arg['margen_ejec']
    margen_ayud = arg['margen_ayud']

    calculate_alarms()
    if len(alarmas):
        Logger.info("%s: Proxima alarma %s" % (APP, alarmas[0]))

    while True:
        # osc.readQueue(oscid)
        # send_date()
        now = datetime.now()
        Logger.debug("%s: %s" % (APP, asctime(localtime())))

        pasadas = [p for p in pasadas if p['inicio'] > now]
        if not len(pasadas):
            Logger.info("No quedan pasadas. Paramos el servicio")
            # notification.notify(
            #     title='Parando el servicio', message='no quedan pasadas',
            #     icon='icon', id=0,
            #     priority=autoclass('android.app.Notification').PRIORITY_MIN,
            #     from_service=True)
            activity.stopSelf()
            break

        update_notification()

        sleep(60)