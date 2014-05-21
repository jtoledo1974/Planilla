package org.jtc.planilla;

import android.util.Log;
import android.app.Activity;
import android.view.WindowManager;
import android.os.Handler;
import android.os.Looper;

public class PlanillaHelper {

    private static final String TAG = "python";
    	
	public static void test() {
		Log.d(TAG, "Heme aquí escribiendo Java para Android");
	}

    public static void setForeground(final Activity activity) {
        Handler handler = new Handler(Looper.getMainLooper());

        handler.post(new Runnable() {
			public void run() {
                Log.d(TAG, "Activity " + activity.toString());
                Log.d(TAG, "Window " + activity.getWindow().toString());
                Log.d(TAG, "LayoutParams " + activity.getWindow().getAttributes().toString());
				activity.getWindow().addFlags(
					WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON|
					WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD|
					WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED|
					WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON);
                Log.d(TAG, "Afteradding " + activity.getWindow().getAttributes().toString());
			}
		});
    }

    public static long testlong(long param) {
    	Log.d(TAG, "Parametro "+param);
    	return param;
    }
}

