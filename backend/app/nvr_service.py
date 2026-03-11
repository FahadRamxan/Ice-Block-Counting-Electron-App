"""NVR operations: login, query recordings for all channels. Uses Dahua NetSDK when available.
Aligned with Duahua_IceFactory_BlockCounter/DahuaRecordingViewer.py (working reference).
"""
from datetime import datetime


def get_recordings_for_date(ip, port, username, password, record_date):
    """Return list of recordings for the given date across all channels.
    Each item: { channel, start_time, end_time, start_ts, end_ts, size }.
    If NetSDK is not available, returns { error: '...' } or empty list for mock.
    """
    try:
        return _get_recordings_sdk(ip, port, username, password, record_date)
    except ImportError:
        return {"error": "Dahua NetSDK not installed. Install the NetSDK wheel in this app's venv (see Duahua_IceFactory_BlockCounter/README.md)."}
    except Exception as e:
        return {"error": str(e)}


def _get_recordings_sdk(ip, port, username, password, record_date):
    from ctypes import sizeof
    from NetSDK.NetSDK import NetClient
    from NetSDK.SDK_Enum import EM_LOGIN_SPAC_CAP_TYPE, EM_QUERY_RECORD_TYPE
    from NetSDK.SDK_Struct import (
        NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY,
        NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY,
        NET_TIME,
        C_LLONG,
    )
    from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect

    # No-op callbacks (required by SDK; same pattern as DahuaRecordingViewer.py)
    def _on_disconnect(login_id, dvr_ip, dvr_port, user):
        pass

    def _on_reconnect(login_id, dvr_ip, dvr_port, user):
        pass

    sdk = NetClient()
    sdk.InitEx(fDisConnect(_on_disconnect))
    sdk.SetAutoReconnect(fHaveReConnect(_on_reconnect))

    in_param = NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY()
    in_param.dwSize = sizeof(NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY)
    in_param.szIP = ip.encode()
    in_param.nPort = int(port)
    in_param.szUserName = username.encode()
    in_param.szPassword = password.encode()
    in_param.emSpecCap = EM_LOGIN_SPAC_CAP_TYPE.TCP
    in_param.pCapParam = None
    out_param = NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY()
    out_param.dwSize = sizeof(NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY)

    login_id, device_info, error_msg = sdk.LoginWithHighLevelSecurity(in_param, out_param)
    if not login_id or (hasattr(login_id, "value") and login_id.value == 0):
        sdk.Cleanup()
        return {"error": error_msg or "Login failed"}

    year, month, day = (int(x) for x in record_date.split("-"))
    start_time = NET_TIME()
    start_time.dwYear, start_time.dwMonth, start_time.dwDay = year, month, day
    start_time.dwHour, start_time.dwMinute, start_time.dwSecond = 0, 0, 0
    end_time = NET_TIME()
    end_time.dwYear, end_time.dwMonth, end_time.dwDay = year, month, day
    end_time.dwHour, end_time.dwMinute, end_time.dwSecond = 23, 59, 59

    all_recordings = []
    n_chan = int(device_info.nChanNum) if hasattr(device_info, "nChanNum") else 16
    for channel in range(n_chan):
        result, file_count, record_infos = sdk.QueryRecordFile(
            login_id,
            channel,
            int(EM_QUERY_RECORD_TYPE.ALL),
            start_time,
            end_time,
            None,
            5000,
            False,
        )
        if not result:
            err = sdk.GetLastErrorMessage() if hasattr(sdk, "GetLastErrorMessage") else None
            if err and not all_recordings:
                sdk.Logout(login_id)
                sdk.Cleanup()
                return {"error": f"Query recordings failed (Ch{channel}): {err}"}
            continue
        if not record_infos or file_count <= 0:
            continue
        for i in range(file_count):
            rec = record_infos[i]
            st = rec.starttime
            et = rec.endtime
            start_ts = f"{st.dwYear}-{st.dwMonth:02d}-{st.dwDay:02d} {st.dwHour:02d}:{st.dwMinute:02d}:{st.dwSecond:02d}"
            end_ts = f"{et.dwYear}-{et.dwMonth:02d}-{et.dwDay:02d} {et.dwHour:02d}:{et.dwMinute:02d}:{et.dwSecond:02d}"
            all_recordings.append({
                "channel": channel,
                "start_time": start_ts,
                "end_time": end_ts,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "size": getattr(rec, "size", 0),
            })
    sdk.Logout(login_id)
    sdk.Cleanup()
    return all_recordings
