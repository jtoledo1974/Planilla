# -*- coding: utf-8 -*-
from kivy.logger import Logger
from jnius import autoclass
from plyer.platforms.android import activity
from android.broadcast import BroadcastReceiver

APP = 'PLANILLA'

Context = autoclass('android.content.Context')
AndroidString = autoclass('java.lang.String')
NotificationBuilder = autoclass('android.app.Notification$Builder')
Drawable = autoclass("{}.R$drawable".format(activity.getPackageName()))
Intent = autoclass('android.content.Intent')
PendingIntent = autoclass('android.app.PendingIntent')


class Vibrator():
    def _get_vibrator_service(self):
        if not hasattr(self, '_vs'):
            self._vs = activity.getSystemService(Context.VIBRATOR_SERVICE)
        print self._vs
        return self._vs

    def vibrate(self, miliseconds):
        self._get_vibrator_service().vibrate(miliseconds)

# TODO Borrar. Esto está sólo para comprobar que tenemos acceso a android
# Vibrator().vibrate(1000)


# Mal fusilado de plyer, pero me aseguro de que funciona
class Notification():
    def notify(self, title='', message='', icon='', id=0, timeout=10,
               priority=None, defaults=False, from_service=False):

        # Parece que Drawable va asociado a los recursos de la aplicación que
        # está corriendo. No tendremos los mismos iconos corriendo como QPython
        # que como Planilla
        if activity.getPackageName() == 'com.hipipal.qpyplus':
            icon = 'icon_notify'
        icon = getattr(Drawable, icon)
        noti = NotificationBuilder(activity)
        if defaults:
            noti.setDefaults(autoclass('android.app.Notification').DEFAULT_ALL)
        noti.setContentTitle(AndroidString(title.encode('utf-8')))
        noti.setContentText(AndroidString(message.encode('utf-8')))
        noti.setSmallIcon(icon)
        noti.setAutoCancel(True)

        if priority is not None:
            noti.setPriority(priority)

        # Logger.debug("Notification: %s" % pformat(
        #     (title, message, priority,  str(mainact), activity.toString())))
        noti.setContentIntent(self._get_pintend())
        # Logger.debug("Notification: %s" % pformat(
        #     (title, message, priority,  mainact.toString(),
        #         activity.toString())))

        self._get_notification_service().notify(id, noti.build())

    def _get_notification_service(self):
        if not hasattr(self, '_ns'):
            self._ns = activity.getSystemService(Context.NOTIFICATION_SERVICE)
        return self._ns

    def _get_pintend(self):
        # activity está definido en plyer.platforms.android, y puede referirse
        # bien a la actividad principal o al servidor. Para el intent
        # necesitamos la actividad principal
        if not hasattr(self, '_pi'):
            intent = activity.getPackageManager().getLaunchIntentForPackage(
                'org.jtc.planilla')  # .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            self._pi = PendingIntent.getActivity(activity, 0, intent, 0)
        return self._pi

notification = Notification()


def toast(text="texto", duration=1):
        Toast = autoclass('android.widget.Toast')
        toast = Toast(activity)
        toast.makeText(activity, text, duration).show()


def fija_alarma(hora, texto):
    Logger.info("%s:Fijando alarma %s %s" % (APP, hora, texto))
    notification.notify(
        title='Planilla',
        message="Fijando alarma %s %s" % (hora, texto), icon='icon')


def broadcast_callback(*args, **kwargs):
    Logger.debug("%s: ESTOY EN EL CALLBACK!!!!!!!!!!!!!!" % APP)

# if __name__ == '__main__':
#     BroadcastReceiver(broadcast_callback, ['HEADSET_PLUG']).start()
