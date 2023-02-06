package com.dziemia.w.androidchatgpt

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material.MaterialTheme
import androidx.compose.material.Surface
import androidx.compose.material.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import com.dziemia.w.androidchatgpt.ui.theme.AndroidChatGPTTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            AndroidChatGPTTheme {
                // A surface container using the 'background' color from the theme
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colors.background
                ) {
                    Greeting(modifier = Modifier.fillMaxSize())
                }
            }
        }
    }
}

@Composable
fun Greeting(modifier: Modifier = Modifier) {
    Column(modifier = modifier) {
        Text(text = "1. ${stringResource(id = R.string.app_name)}")
        Text(text = "2. ${stringResource(id = R.string.hello_world)}")
        Text(text = "3. ${stringResource(id = R.string.goodbye_world)}")
        Text(text = "4. ${stringResource(id = R.string.save_to_usb)}")
        Text(text = "5. ${stringResource(id = R.string.save_to_disk)}")
    }
}

@Preview(name = "American English", showBackground = true, locale = "en-rUS")
@Preview(name = "British English", showBackground = true, locale = "en-rGB")
@Preview(name = "Polish", showBackground = true, locale = "pl")
@Preview(name = "Ukrainian", showBackground = true, locale = "uk")
@Composable
fun DefaultPreview() {
    AndroidChatGPTTheme {
        Greeting()
    }
}