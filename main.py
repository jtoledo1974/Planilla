# -*- coding: utf-8 -*-

import pickle
from datetime import datetime, time, timedelta
from copy import copy
from functools import partial
from pprint import pformat

from kivy.app import App
from kivy.config import Config
from kivy.uix.button import Button
from kivy import platform
from kivy.logger import Logger
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.animation import Animation
from kivy.vector import Vector
from kivy.uix.screenmanager import Screen, RiseInTransition, FallOutTransition, \
    NoTransition
from kivy.uix.relativelayout import RelativeLayout
from kivy.properties import NumericProperty, ObjectProperty, StringProperty, \
    ListProperty

if platform == 'android':
    Logger.debug('PLANILLA: Importando %s' % datetime.now())
    import android
    from plyer.platforms.android import activity
    from jnius import autoclass
    from android.runnable import run_on_ui_thread

if platform == 'win':
    Config.set('graphics', 'width', 480)
    Config.set('graphics', 'height', 756)

# Necesito poder cambiar la hora actual con facilidad para poder hacer pruebas
# durante usando horas arbitrarias.
odt = datetime


class datetime(odt):
    @staticmethod
    def now():
        return odt.now()
#       return odt.now()-timedelta(hours=11)

APP = 'PLANILLA'


class MainButton(Button):
    pass


class Horario():

    pasadas = []
    inicio = None
    final = None
    s1 = 'S1'  # Así es como se carga inicialmente
    s2 = 'S2'

    def __init__(self, nucleo, numero, s1, s2):

        self.pasadas = []
        self.s1 = s1
        self.s2 = s2
        self._horarios = {}
        self._sectores = {}

        now = datetime.now()

        # Cargamos la planilla del csv
        with open("Planilla.csv", "r") as f:
            csv = f.readlines()
        self._horarios['TMA'] = {
            int(l[0]): [c for c in l[1:].rstrip('\n').split(',') if c != '']
            for l in csv[2:10]}
        self._horarios['Ruta'] = {
            int(l[0]): [c for c in l[1:].rstrip('\n').split(',') if c != '']
            for l in csv[13:21]}
        self._sectores['TMA'] = [
            c for c in csv[0].rstrip('\n').split(',') if c != ''][1:]
        self._sectores['Ruta'] = [
            c for c in csv[11].rstrip('\n').split(',') if c != ''][1:]

        numero = int(numero)
        text = self._horarios[nucleo][numero]

        while True:
            if len(text) == 0:
                break
            (starth, startm) = [int(c) for c in text[0].split(':')]
            (finishh, finishm) = [int(c) for c in text[1].split(':')]
            task = text[2]
            sector = ''
            if task != 'Libre':
                sector = getattr(self, task[-2:].lower())
                task = 'Ejecutivo' if task[0] == 'E' else 'Ayudante'
            text = text[3:]
            self.pasadas.append({
                'inicio': datetime.combine(now, time(starth, startm)),
                'final': datetime.combine(now, time(finishh, finishm)),
                'task': task, 'sector': sector})

        # Identificar si vamos a hacer turno de mañana o tarde
        if datetime.combine(now, time(6, 30)) < now < \
                datetime.combine(now, time(14, 30)):
            Logger.debug("%s: Turno de mañana" % APP)
            offset = timedelta(hours=7, minutes=30)
        elif datetime.combine(now, time(14, 30)) < now < \
                datetime.combine(now, time(22, 30)):
            Logger.debug("%s: Turno de tarde" % APP)
            offset = timedelta(hours=15)
        else:  # Al día siguiente
            Logger.debug("%s: Turno de mañana del día siguiente" % APP)
            # TODO pensarse en levantar excepción ValueError, no tiene mucho
            # sentido
            offset = timedelta(hours=31, minutes=30)

        # Ajustar cada bloque al turno que vamos a hacer, de mañana de hoy o
        # tarde de hoy self.pasadas.sort(). Para garantizar que el primer
        # elemento es el más temprano
        start = (self.pasadas[0])['inicio']-datetime.combine(now, time(0, 0))
        self.pasadas = [{
                        'inicio': b['inicio']-start+offset,
                        'final': b['final']-start+offset,
                        'task': b['task'],
                        'sector': b['sector']} for b in self.pasadas]
        self.inicio = (self.pasadas[0])['inicio']
        self.final = (self.pasadas[-1])['final']

    def actualiza_sector(self, new, num_sector):
        old = getattr(self, num_sector)
        self.pasadas = [{
                        'inicio': p['inicio'],
                        'final': p['final'],
                        'task': p['task'],
                        'sector': new if p['sector'] == old else p['sector']}
                        for p in self.pasadas]
        setattr(self, num_sector, new)
        Logger.debug("%s: Nuevo sector %s es %s" % (APP, num_sector, new))

    def __str__(self):
        str = ""
        for b in self.pasadas:
            str = str+"\n%02d:%02d\n  %s%s" % (b['inicio'].hour,
                                               b['inicio'].minute,
                                               b['task'],
                                               ' '+b['sector'])
        str = str+"\n%02d:%02d" % (self.pasadas[-1]['final'].hour,
                                   self.pasadas[-1]['final'].minute)
        return str

    def pasadas_pendientes(self, margen):
        now = datetime.now()
        return [p for p in self.pasadas
                if p['inicio'] > (now+timedelta(minutes=margen))]

    def sectores(self, nucleo=''):
        assert nucleo
        return self._sectores[nucleo]

    def n_sectores(self):
        d = {p['sector']: '' for p in self.pasadas if p['sector'] != ''}
        return len(d.keys())


class NucleoPopup(Popup):
    def __init__(self, **kwargs):
        super(Popup, self).__init__(**kwargs)
        self.ids.ruta.bind(on_press=self.fija_nucleo)
        self.ids.tma.bind(on_press=self.fija_nucleo)
        self.config = kwargs['config']

    def fija_nucleo(self, instance):
        Logger.debug('En el Popup callback con value %s' % instance.text)
        self.config.set('general', 'nucleo', instance.text)
        self.dismiss()
        self.config.write()


class SectoresScreen(Screen):
    def add_sectors(self, sectores=(), n_sectores=0):
        assert sectores != () and n_sectores > 0
        for s in sectores:
            self.gridlayout.add_widget(Button(text=s))


class AlarmScreen(Screen):

    r = NumericProperty(100)    # Radio del círculo
    ra = NumericProperty(1.0)   # Alfa del círculo
    r2 = NumericProperty(100)   # Radio del círculo que marca pulsación
    r2a = NumericProperty(0)    # Alfa del círculo que marca pulsación
    cd = NumericProperty(0.0)   # Offset de los círculos que se desplazan
    ca = NumericProperty(1.0)   # Alfa de los círculos que se desplazan
    R = 0.08                    # Constante para calcular el tamaño
    motion_uid = None

    def on_height(self, widget, height):
        self.r = height*self.R
        self.r2 = height*self.R

    def on_enter(self, *args):
        Logger.debug("%s: AlarmScreen.on_enter self.width=%s %s" % (
            APP, self.width, datetime.now()))
        if self.width < 100:
            width = 480  # No debería hacer falta, pero la primera vez falla
        else:
            width = self.width
        self.cd = 0
        self.ca = 0
        self.anim = Animation(cd=width/2, ca=1, d=1, t='in_quad') \
            + Animation(cd=0, ca=0, d=0)
        self.anim.repeat = True
        self.anim.start(self)

        self.app.reproducir_sonido_alarma()
        self.app.clock_callback = partial(
            self.app.cancelar_alarma,
            source='Clock', clock_date=datetime.now())
        Clock.schedule_once(self.app.clock_callback, self.app.ACS)  # segundos

    def on_leave(self, *args):
        self.anim.stop(self)
        Logger.debug("%s: AlarmScreen.on_leave %s" % (APP, datetime.now()))
        if platform == 'android':
            self.app.reset_window_flags()  # Permitir apagado automático

    def on_touch_down(self, touch):
        if Vector(touch.pos).distance(
           Vector(self.center_x, self.height*0.2)) < 2*self.r:
            self.motion_uid = touch.uid
            self.r2a = 1.0
            self.r2 = self.height*self.R
            anim = Animation(
                r2=self.height*self.R*2, r2a=0, t='in_quad', d=0.6)
            anim.start(self)

    def on_touch_move(self, touch):
        if touch.uid == self.motion_uid:
            # Cancelar si de desplaza más de la mitad de la distancia al borde
            self.ra = 1-2.5*Vector(touch.pos).distance(
                Vector(self.center_x, self.height*0.2))/self.width
            if self.ra < 0.05:
                self.ra = 1
                self.app.cancelar_alarma(source='user')

    def on_touch_up(self, touch):
        if touch.uid == self.motion_uid:
            self.ra = 1


class PlanillaWidget(RelativeLayout):

    horario = ObjectProperty()

    def on_horario(self, widget, horario):
        pass


class PlanillaScreen(Screen):
    numero = NumericProperty(0)
    horario = ObjectProperty()
    s1 = StringProperty('Sector1')
    s2 = StringProperty('Sector2')
    sectores = ListProperty(['DDI', 'XAL', 'FINAL'])
    textohorario = StringProperty('')

    def on_enter(self, *args):
        self.ids.pw.horario = self.horario
        self.ids.ss1.bind(text=self.s1_changed)
        self.ids.ss2.bind(text=self.s2_changed)

    def s1_changed(self, spinner, s1):
        Logger.debug("%s: Nuevo S1 %s" % (APP, s1))
        self.horario.actualiza_sector(s1, 's1')
        self.ids.pw.horario = copy(self.horario)
        self.horario = copy(self.horario)

    def s2_changed(self, spinner, s2):
        Logger.debug("%s: Nuevo S2 %s" % (APP, s2))
        self.horario.actualiza_sector(s2, 's2')
        self.ids.pw.horario = copy(self.horario)
        self.horario = copy(self.horario)


class PlanillaApp(App):

    arrancando = False
    service = None       # Referencia al servicio de Android
    br = None            # Background Receiver
    en_alarma = False    # La pantalla de alarma está corriendo

    ACS = 20             # Alarm Cancel Seconds - Cancelación automática

    planilla = None
    alarmscreen = None
    sectoresscreen = None

    def build(self):
        self.use_kivy_settings = False
        return self.root

    def build_config(self, config):
        config.setdefaults('general', {
            'nucleo': 'INDEFINIDO',
            'margen_ejec': 10,
            'margen_ayud': 5,
            'numero': 0,
            's1': 'Sector1',
            's2': 'Sector2'})

    def build_settings(self, settings):
        settings.add_json_panel('Planilla', self.config, 'settings.json')

    def on_pause(self):
        if self.en_alarma:
            self.cancelar_sonido_alarma()
        return True

    def on_resume(self):
        Logger.debug("%s: On resume %s" % (APP, datetime.now()))
        if self.en_alarma:
            self.reproducir_sonido_alarma()

    def on_new_intent(self, intent):
        Logger.debug("%s: on_new_intent %s %s" % (
            APP, datetime.now(), intent))
        if intent:
            bundle = intent.getExtras()
            if bundle:
                self.set_window_flags()  # Para que la alarma encienda el movil
                self.sonar_alarma(
                    texto=bundle.getString('texto'))

    def on_keypress(self, window, keycode1, keycode2, text, modifiers):
        # Gestión del botón atrás.
        # Logger.debug("%s: on_keypress k1: %s, k2: %s, text: %s, mod: %s" % (
        #     APP, keycode1, keycode2, text, modifiers))
        if self.en_alarma and keycode1 == 27:  # escape
            self.cancelar_alarma(source="on_keypress")
            return True
        elif self.en_alarma and keycode1 == 1001:  # Back button
            return True  # Backbutton no hace nada durante la alarma
        elif keycode1 in [27, 1001]:
            Logger.debug("Pulsado el boton BACK")
            if platform == 'android':
                activity.moveTaskToBack(True)
            return True
        return False

    def on_start(self):
        # TEMPORAL!!! QUITAR!!!
        # if platform == 'android':
        #     android.map_key(android.KEYCODE_POWER, 1002)
        #     android.map_key(android.KEYCODE_BACK, 1001)
        # from kivy.core.window import Window
        # Window.bind(on_keyboard=self.on_keypress)
        # self.sonar_alarma(texto='Alarma de prueba on_start')
        # return
        Logger.debug("%s: on_start %s" % (APP, datetime.now()))

        self.scmgr = self.root.scmgr  # scmgr identificado con id en el kv

        if self.config.get('general', 'nucleo') not in ('Ruta', 'TMA'):
            self.pedir_nucleo()

        numero = int(self.config.get('general', 'numero'))
        if numero != 0:  # 0 indica que no estamos rearrancando
            # Evita que cambiar s1 y s2 arranque el servicio
            self.arrancando = True
            self.asigna_numero(numero)

        if platform == 'android':
            android.map_key(android.KEYCODE_BACK, 1001)
        from kivy.core.window import Window
        Window.bind(on_keyboard=self.on_keypress)

        if platform == 'android':
            import android.activity as python_activity
            python_activity.bind(on_new_intent=self.on_new_intent)
            # on_new_intent sólo se llama cuando la aplicación ya está
            # arrancada. Para no duplicar código la llamamos desde aquí
            self.on_new_intent(activity.getIntent())

        n = int(self.config.get('general', 'numero'))
        if n:
            # Arrancar con la planilla puesta ya
            # self.scmgr.transition = NoTransition()
            # self.scmgr.current = 'planilla'
            self.asigna_numero(n)

    def on_stop(self):
        if platform == 'android' and self.br:
            self.br.stop()

    def pedir_nucleo(self):
            popup = NucleoPopup(config=self.config)
            popup.open()

    if platform == 'android':
        @run_on_ui_thread
        def set_window_flags(self):
            # Cuando salta la alarma es necesario que se encienda el móvil
            # El servicio llama a la actividad, que como tiene estos parámetros
            # enciende el móvil. El servicio por su parte coge un wake lock
            # porque si no cuando el usuario ha apagado el móvil con Planilla
            # en foreground Android no vuelve a encender al llamar a la app
            LayoutParams = autoclass('android.view.WindowManager$LayoutParams')
            activity.getWindow().addFlags(
                LayoutParams.FLAG_KEEP_SCREEN_ON |
                LayoutParams.FLAG_DISMISS_KEYGUARD |
                LayoutParams.FLAG_SHOW_WHEN_LOCKED |
                LayoutParams.FLAG_TURN_SCREEN_ON)

        @run_on_ui_thread
        def reset_window_flags(self):
            LayoutParams = autoclass('android.view.WindowManager$LayoutParams')
            activity.getWindow().clearFlags(
                LayoutParams.FLAG_KEEP_SCREEN_ON |
                LayoutParams.FLAG_DISMISS_KEYGUARD |
                LayoutParams.FLAG_SHOW_WHEN_LOCKED |
                LayoutParams.FLAG_TURN_SCREEN_ON)

    def asigna_numero(self, numero):
        # self.cancelar_alarma(source="pruebas")
        # self.sonar_alarma(texto="asgina_numero")
        # return

        if not self.sectoresscreen:
            self.sectoresscreen = SectoresScreen()
            self.scmgr.add_widget(self.sectoresscreen)
            self.scmgr.current = 'sectores'

        nucleo = self.config.get('general', 'nucleo')
        s1 = self.config.get('general', 's1')
        s2 = self.config.get('general', 's2')

        horario = Horario(nucleo=nucleo, numero=numero, s1=s1, s2=s2)
        n_sectores = horario.n_sectores()
        self.sectoresscreen.add_sectors(
            sectores=horario.sectores(nucleo), n_sectores=n_sectores)
        self.horario = horario
        return

        if not self.planilla:
            self.planilla = PlanillaScreen()
            self.scmgr.add_widget(self.planilla)
            self.planilla.bind(horario=self.horario_cambiado)

        numero = int(numero)
        try:
            self.planilla.numero = numero
            nucleo = self.config.get('general', 'nucleo')
            s1 = self.config.get('general', 's1')
            s2 = self.config.get('general', 's2')
            self.planilla.horario = self.horario
            self.planilla.sectores = self.horario.sectores(nucleo)
            self.planilla.ids.ss1.text = self.config.get('general', 's1')
            self.planilla.ids.ss2.text = self.config.get('general', 's2')
            self.scmgr.transition = RiseInTransition()
            self.scmgr.current = 'planilla'
            self.config.set('general', 'numero', numero)
            self.config.write()
        except KeyError:
            self.pedir_nucleo()
        except ValueError:
            #  Ver el raise en planilla.__init__
            print("No es hora, quillo")
        self.arrancando = False
        self.arrancar_servicio()

    # Callback cuando cambian sectores
    def horario_cambiado(self, instance, horario):
        if self.arrancando is False:
            self.config.set('general', 's1', horario.s1)
            self.config.set('general', 's2', horario.s2)
            self.config.write()
            self.arrancar_servicio()

    def parar_servicio(self):
        self.cancelar_alarma(source='parar_servicio')
        if platform == 'android' and self.service:
            Logger.debug("%s: Parando el servicio" % APP)
            self.service.stop()
        self.service = None

    def arrancar_servicio(self):
        self.parar_servicio()
        margen_ejec = int(self.config.get('general', 'margen_ejec'))
        margen_ayud = int(self.config.get('general', 'margen_ayud'))
        pasadas = self.planilla.horario.pasadas_pendientes(0)
        # Logger.debug("%s: Pasadas pendientes %s" % (APP, pasadas))
        arg = {'margen_ejec': margen_ejec,
               'margen_ayud': margen_ayud, 'pasadas': pasadas}
        arg = pickle.dumps(arg)

        if platform == 'android':
            self.service = android.AndroidService(
                'Planilla: activando alarmas', 'Servicio iniciado')
            self.service.start(arg)
            Logger.debug("%s: Servicio arrancado" % APP)

    def _get_audiomanager(self):
        if not hasattr(self, 'audiomanager'):
            if platform == 'android':
                Context = autoclass('android.content.Context')
                self.audiomanager = activity.getSystemService(
                    Context.AUDIO_SERVICE)
        return self.audiomanager

    def _get_ringtone(self):
        if not hasattr(self, 'ringtone'):
            if platform == 'android':
                RingtoneManager = autoclass('android.media.RingtoneManager')
                AudioManager = autoclass('android.media.AudioManager')

                u = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
                self.ringtone = RingtoneManager.getRingtone(
                    activity.getApplicationContext(), u)
                self.ringtone.setStreamType(AudioManager.STREAM_ALARM)
            else:
                from kivy.core.audio import SoundLoader
                self.ringtone = SoundLoader().load(
                    '\windows\media\windows logon sound.wav')
        return self.ringtone

    def _get_vibrator(self):
        if not hasattr(self, 'vibrator') and platform == 'android':
            Context = autoclass('android.content.Context')
            self.vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)
        return self.vibrator

    def reproducir_sonido_alarma(self):
        # Necesitamos separarar los sonidos de la alarma de la presentación de
        # la alarma para que la pausa de la aplicación quite los ruidos
        # sin cancelar la alarma propiamente dicha, puesto que a veces
        # android nos pausa y despausa sin motivo aparente
        if platform == 'android':
                AudioManager = autoclass('android.media.AudioManager')
                am = self._get_audiomanager()
                am.setStreamVolume(
                    AudioManager.STREAM_ALARM,
                    am.getStreamMaxVolume(AudioManager.STREAM_ALARM), 0)
                self.ringer_mode = am.getRingerMode()
                am.setRingerMode(AudioManager.RINGER_MODE_NORMAL)

        self._get_ringtone().play()

        if platform == 'android':
            self._get_vibrator().vibrate([0, 500.0, 500.0], 1)

    def cancelar_sonido_alarma(self):
        assert hasattr(self, 'ringer_mode')
        self._get_ringtone().stop()
        if platform == 'android':
            self._get_audiomanager().setRingerMode(self.ringer_mode)
            self._get_vibrator().cancel()

    def sonar_alarma(self, texto='Alarma'):
        ltext = str(datetime.now())
        Logger.debug("%s: sonar_alarma: %s %s" % (APP, texto, ltext))

        if self.en_alarma:
            Logger.debug("%s: Alarma ya activa. Olvidar" % APP)
            return

        if not self.alarmscreen:
            self.alarmscreen = AlarmScreen()
            self.alarmscreen.app = self
            self.scmgr.add_widget(self.alarmscreen)

        self.previous_screen = self.scmgr.current
        self.scmgr.transition = NoTransition()
        self.scmgr.current = 'alarma'
        self.alarmscreen.ids.alarmbutton.text = texto

        # La alarma propiamente dicha se activa en el on_enter de AlarmScreen
        self.en_alarma = True

    def cancelar_alarma(self, dt=None, source='Unknown', clock_date=None):
        # argumento dt viene del Clock
        now = datetime.now()
        Logger.debug("%s: cancelar_alarma - source %s %s" % (APP, source, now))

        if not self.en_alarma:
            # La cancelación automática se llama aunque el usuario haya
            # cancelado ya. No hacer nada si es el caso
            Logger.debug(
                "%s: cancelar_alarma - alarma ya apagada." % APP)
            return

        if source == 'Clock':
            # El usuario no ha cancelado. Debemos evitar que la pantalla
            # se quede encendida. Enviamos la task al background
            Logger.debug("%s: cancelar alarma clock_date=%s dt=%s" % (
                APP, clock_date, dt))
            if (now-clock_date).seconds < self.ACS:
                # No sé por qué a veces el Clock llama inmediatamente en
                # lugar de esperar los segundos que tocan. Si es el caso
                # volver a intentarlo con lo que falta
                self.clock_callback = partial(
                    self.cancelar_alarma, source='Clock',
                    clock_date=clock_date)
                Clock.schedule_once(self.clock_callback,
                                    (clock_date + timedelta(seconds=self.ACS)
                                     - now).seconds)
                Logger.debug(
                    "%s: cancelar_alarma - Clock llamo antes de tiempo")
                return

        self.cancelar_sonido_alarma()
        self.scmgr.transition = FallOutTransition()
        self.scmgr.current = self.previous_screen
        Clock.unschedule(self.clock_callback)
        self.en_alarma = False

    def cancelar(self):
        self.scmgr.transition = FallOutTransition()
        self.scmgr.current = "principal"
        self.parar_servicio()

        self.config.set('general', 'numero', 0)
        self.config.set('general', 's1', 'Sector1')
        self.config.set('general', 's2', 'Sector2')
        self.config.write()


class TestApp(App):
    def build(self):
        return Button(text='hello world 2')

    def on_start(self):
        Logger.debug("on_start TestApp")
        ph = autoclass('org.jtc.planilla.PlanillaHelper')()
        S = autoclass('java.lang.System')
        l = S.currentTimeMillis()
        import sys
        l = sys.maxint*2
        # Logger.debug("%s"%dir(ph))
        Logger.debug("testlong %s %s" % (l, str(ph.testlong(l))))

if __name__ == '__main__':
    PlanillaApp().run()
    # TestApp().run()
