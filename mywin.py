# -*- coding: utf-8 -*-
from kivy.logger import Logger
from plyer import notification

APP = 'PLANILLA'


def toast(*args):
    pass


def fija_alarma(hora, texto):
    Logger.info("%s:Fijando alarma %s %s" % (APP, hora, texto))
    notification.notify(
        title='Planilla', message="Fijando alarma %s %s" % (hora, texto))
