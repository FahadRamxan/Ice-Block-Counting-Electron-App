"""Dahua NetSDK: login, query recordings per channel, all channels for a date."""
import os
from datetime import datetime
from ctypes import sizeof

def _sdk_available():
    try:
        from NetSDK.NetSDK import NetClient
        return True
    except ImportError:
        return False

def get_recordings_for_date(ip, port, username, password, record_date, channel):
    """Single channel. record_date YYYY-MM-DD. Returns list of dicts or {error}."""
    if not _sdk_available():
        return {"error": "Dahua NetSDK not installed. pip install NetSDK wheel into venv."}
    from NetSDK.NetSDK import NetClient
    from NetSDK.SDK_Enum import EM_LOGIN_SPAC_CAP_TYPE, EM_QUERY_RECORD_TYPE
    from NetSDK.SDK_Struct import (
        NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY,
        NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY,
        NET_TIME,
        C_LLONG,
    )
    from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect

    sdk = NetClient()
    disc = fDisConnect(lambda *a: None)
    sdk.InitEx(disc)
    sdk.SetAutoReconnect(fHaveReConnect(lambda *a: None))
    login_id = C_LLONG()
    try:
        inp = NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY()
        inp.dwSize = sizeof(NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY)
        inp.szIP = ip.encode()
        inp.nPort = int(port)
        inp.szUserName = username.encode()
        inp.szPassword = password.encode()
        inp.emSpecCap = EM_LOGIN_SPAC_CAP_TYPE.TCP
        inp.pCapParam = None
        out = NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY()
        out.dwSize = sizeof(NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY)
        login_id, _, err = sdk.LoginWithHighLevelSecurity(inp, out)
        if not login_id:
            return {"error": err or "Login failed"}
        y, m, d = map(int, record_date.split("-")[:3])
        st = NET_TIME()
        st.dwYear, st.dwMonth, st.dwDay = y, m, d
        st.dwHour, st.dwMinute, st.dwSecond = 0, 0, 0
        et = NET_TIME()
        et.dwYear, et.dwMonth, et.dwDay = y, m, d
        et.dwHour, et.dwMinute, et.dwSecond = 23, 59, 59
        ok, n, infos = sdk.QueryRecordFile(
            login_id, int(channel), int(EM_QUERY_RECORD_TYPE.ALL), st, et, None, 5000, False
        )
        if not ok:
            return {"error": sdk.GetLastErrorMessage() or "Query failed"}
        out_list = []
        for i in range(n):
            r = infos[i]
            out_list.append({
                "channel": channel,
                "start_time": f"{r.starttime.dwHour:02d}:{r.starttime.dwMinute:02d}:{r.starttime.dwSecond:02d}",
                "end_time": f"{r.endtime.dwHour:02d}:{r.endtime.dwMinute:02d}:{r.endtime.dwSecond:02d}",
                "start_ts": f"{r.starttime.dwYear}-{r.starttime.dwMonth:02d}-{r.starttime.dwDay:02d} {r.starttime.dwHour:02d}:{r.starttime.dwMinute:02d}:{r.starttime.dwSecond:02d}",
                "end_ts": f"{r.endtime.dwYear}-{r.endtime.dwMonth:02d}-{r.endtime.dwDay:02d} {r.endtime.dwHour:02d}:{r.endtime.dwMinute:02d}:{r.endtime.dwSecond:02d}",
                "size": getattr(r, "size", 0) or 0,
            })
        return out_list
    finally:
        if login_id:
            try:
                sdk.Logout(login_id)
            except Exception:
                pass
        try:
            sdk.Cleanup()
        except Exception:
            pass

def get_recordings_all_channels(ip, port, username, password, record_date, channels_filter=None):
    """
    channels_filter: None = all channels (0..n-1 from device), or list of int channel indices.
    Returns { nvr_channels, recordings_by_channel: { "0": [...], "1": [...] }, error? }
    """
    if not _sdk_available():
        return {"error": "NetSDK not installed", "recordings_by_channel": {}}
    from NetSDK.NetSDK import NetClient
    from NetSDK.SDK_Enum import EM_LOGIN_SPAC_CAP_TYPE, EM_QUERY_RECORD_TYPE
    from NetSDK.SDK_Struct import (
        NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY,
        NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY,
        NET_TIME,
        C_LLONG,
    )
    from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect

    sdk = NetClient()
    sdk.InitEx(fDisConnect(lambda *a: None))
    sdk.SetAutoReconnect(fHaveReConnect(lambda *a: None))
    login_id = C_LLONG()
    recordings_by_channel = {}
    try:
        inp = NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY()
        inp.dwSize = sizeof(NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY)
        inp.szIP = ip.encode()
        inp.nPort = int(port)
        inp.szUserName = username.encode()
        inp.szPassword = password.encode()
        inp.emSpecCap = EM_LOGIN_SPAC_CAP_TYPE.TCP
        out = NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY()
        out.dwSize = sizeof(NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY)
        login_id, dev, err = sdk.LoginWithHighLevelSecurity(inp, out)
        if not login_id:
            return {"error": err or "Login failed", "recordings_by_channel": {}}
        n_ch = int(dev.nChanNum) if dev else 16
        y, m, d = map(int, record_date.split("-")[:3])
        st = NET_TIME()
        st.dwYear, st.dwMonth, st.dwDay = y, m, d
        st.dwHour, st.dwMinute, st.dwSecond = 0, 0, 0
        et = NET_TIME()
        et.dwYear, et.dwMonth, et.dwDay = y, m, d
        et.dwHour, et.dwMinute, et.dwSecond = 23, 59, 59
        ch_list = channels_filter if channels_filter is not None else list(range(n_ch))
        for ch in ch_list:
            if ch < 0 or ch >= n_ch:
                continue
            ok, n, infos = sdk.QueryRecordFile(
                login_id, ch, int(EM_QUERY_RECORD_TYPE.ALL), st, et, None, 5000, False
            )
            if not ok:
                recordings_by_channel[str(ch)] = {"error": sdk.GetLastErrorMessage()}
                continue
            rows = []
            for i in range(n):
                r = infos[i]
                rows.append({
                    "start_ts": f"{r.starttime.dwYear}-{r.starttime.dwMonth:02d}-{r.starttime.dwDay:02d} {r.starttime.dwHour:02d}:{r.starttime.dwMinute:02d}:{r.starttime.dwSecond:02d}",
                    "end_ts": f"{r.endtime.dwYear}-{r.endtime.dwMonth:02d}-{r.endtime.dwDay:02d} {r.endtime.dwHour:02d}:{r.endtime.dwMinute:02d}:{r.endtime.dwSecond:02d}",
                    "size": getattr(r, "size", 0) or 0,
                })
            recordings_by_channel[str(ch)] = rows
        return {
            "nvr_channels": n_ch,
            "recordings_by_channel": recordings_by_channel,
            "date": record_date,
        }
    finally:
        if login_id:
            try:
                sdk.Logout(login_id)
            except Exception:
                pass
        try:
            sdk.Cleanup()
        except Exception:
            pass
