from jnius import autoclass, cast
from plyer.platforms.android import activity
String = autoclass('java.lang.String')
Context = autoclass('android.content.Context')
Intent = autoclass('android.content.Intent')
PendingIntent = autoclass('android.app.PendingIntent')
System = autoclass('java.lang.System')
SystemClock = autoclass('android.os.SystemClock')
AlarmManager = autoclass('android.app.AlarmManager')

am = activity.getSystemService(Context.ALARM_SERVICE)
intent = Intent(String('org.jtc.planilla.SERVICEALARM')).putExtra("id", 0)
pi = PendingIntent.getBroadcast(activity, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT)

ms = 10  # ms anadidos al elapsed real time del movil
ert = SystemClock.elapsedRealtime()

am.set(AlarmManager.ELAPSED_REALTIME_WAKEUP,
       ert + ms, pi)
