package com.example.haha

import android.app.Application
import com.example.haha.network.RetrofitClient

class HaHaApp : Application() {

    override fun onCreate() {
        super.onCreate()
        RetrofitClient.init(this)
    }
}
