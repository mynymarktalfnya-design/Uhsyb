"""Windows Service wrapper for the persistent MMF local queue service.

Install pywin32 first, then run as Administrator:
  python mmf_windows_service.py install
  python mmf_windows_service.py start
"""
import os
import sys

import win32event
import win32service
import win32serviceutil

from mmf_local_service import HOST, PORT, main


class MMFLocalQueueService(win32serviceutil.ServiceFramework):
    _svc_name_ = "MMFLocalQueueService"
    _svc_display_name_ = "Mini Market الفنية Offline Queue"
    _svc_description_ = "Persistent offline queue and synchronisation service for Mini Market الفنية."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        main()


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("This wrapper must be installed on Windows")
    win32serviceutil.HandleCommandLine(MMFLocalQueueService)
