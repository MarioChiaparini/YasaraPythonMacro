# YASARA PLUGIN
# TOPIC:       Utilities
# TITLE:       YaPyCon
# AUTHOR:      Athanasios Anastasiou
# LICENSE:     GPL
# DESCRIPTION: YASARA Python Console
# PLATFORMS:   Windows, Linux

"""
MainMenu: Window
  PullDownMenu after Update frequency: Python Console
    Request: YaPyCon
"""

try:
    import yasara
except ImportError:
    pass

import sys
import threading

try:
    HAS_QTCONSOLE = True
    from qtconsole.rich_jupyter_widget import RichJupyterWidget
    from qtconsole.manager import QtKernelManager
except ImportError:
    HAS_QTCONSOLE = False

try:
    HAS_IPYTHON = True
    from IPython.lib import guisupport
except ImportError:
    HAS_IPYTHON = False

try:
    HAS_RPYC = True
    from rpyc.utils.server import OneShotServer, ThreadedServer
    from rpyc import Service
except ImportError:
    HAS_RPYC = False

    class Service:
        """
        Substitutes for rpyc's Service so that derived classes do not fail to initialise.
        """
        pass


class YasaraContextRelayService(Service):
    """
    An rpyc service that establishes a "bridge" between the YaPyConsole plugin and subsequent processes.

    Notes:
        * This object is  basically a "proxy" between data in the context of the plugin process and the context
          of subsequent processes.
        *  Although this object is entirely "visible" through the console, it is not meant to be used directly.
    """
    def __init__(self, connection_info=None):
        super().__init__()
        self._output_stream = sys.stdout
        self._plugin = yasara.plugin
        self._request = yasara.request
        self._opsys = yasara.opsys
        self._version = yasara.version
        self._serialnumber = yasara.serialnumber
        self._stage = yasara.stage
        self._owner = yasara.owner
        self._permissions = yasara.permissions
        self._workdir = yasara.workdir
        self._selection = yasara.selection
        self._com = yasara.com
        self._connection_info = connection_info

    def exposed_get_plugin(self):
        return self._plugin

    def exposed_get_request_str(self):
        return self._request

    def exposed_get_opsys(self):
        return self._opsys

    def exposed_get_version(self):
        return self._version

    def exposed_get_serialnumber(self):
        return self._serialnumber

    def exposed_get_stage(self):
        return self._stage

    def exposed_get_owner(self):
        return self._owner

    def exposed_get_permissions(self):
        return self._permissions

    def exposed_get_workdir(self):
        return self._workdir

    def exposed_get_selection(self):
        return self._selection

    def exposed_get_com(self):
        return self._com

    def exposed_get_connection_info(self):
        return self._connection_info

    def exposed_stdout_relay(self, payload):
        self._output_stream.write(payload)
        self._output_stream.flush()


class RpcServerThread(threading.Thread):
    """
    Maintains the rpyc thread which allows the console process to interface with the context of the originating process.
    """
    def __init__(self, *args, **kwargs):
        """
        Initialises the underlying YasaraContextRelayService that the thread is serving.

        :param args: List of positional parameters to YasaraContextRelayService
        :type args: list
        :param kwargs: Dictionary of named parameters to YasaraContextRelayService.
        :type kwargs: dict
        """
        super().__init__()
        # Notice here that the ThreadedServer is serving AN INSTANCE (not the class itself),
        # this means that all subsequent processes would share THIS particular set of information.
        self._serv_object = ThreadedServer(YasaraContextRelayService(*args, **kwargs),
                                           port=18861,
                                           protocol_config={"allow_public_attrs": True})

    def run(self):
        """
        Launches the RPC ThreadedServer.
        """
        # The ThreadedServer is started and blocks here (as per rpyc)
        self._serv_object.start()

    def stop_server(self):
        # stop_server is called from the main thread effectively terminating RpcServerThread
        self._serv_object.close()


def yapycon_plugin_check_if_disabled():
    """
    Checks if YaPyCon can launch.

    Notes:
        * This function checks if it was possible for YaPyCon to load certain pre-requisite modules.
        * If these modules were not found, this function will signal this to YASARA (by returning a 1) and subsequently,
          YaPyCon's menu option ("Python Console") will not be available in YASARA.

    :returns: Either 0 or 1 to signal Success or Failure to launch respectively.
    :rtype: int
    """
    if not (HAS_IPYTHON or HAS_RPYC or HAS_QTCONSOLE):
        return 1

    return 0


def yapycon_launch_plugin(plugin_request):
    """
    Handles the initialisation and launching of the YaPyCon plugin.

    :param plugin_request: The request string sent by YASARA when the plugin is launched.
    :type plugin_request: str
    """
    # TODO: MID, intercept "CheckIfDisabled" and return an informative message to YASARA if the console cannot be launched.
    if plugin_request == "YaPyCon":
        # Create (or get) the qt handle for the console "app".
        app = guisupport.get_app_qt4()
        app.setApplicationName("YASARA Python Console (YaPyCon)")

        # Create the kernel "process"
        # NOTE: QtKernelManager works too (In addition it also generates a proper key)
        # TODO: MID, Add an option to be able to just launch the kernel without creating the widget.
        kernel_manager = QtKernelManager()
        kernel_manager.start_kernel()

        # Create the client "process"
        kernel_client = kernel_manager.client()
        kernel_client.start_channels()

        # This creates the widget (which is not strictly necessary for the kernel)
        control = RichJupyterWidget()
        control.kernel_manager = kernel_manager
        control.kernel_client = kernel_client
        # Connect the fact that exit was requested to closing the window
        control.exit_requested.connect(app.quit)
        # Widget goes to visible
        control.show()
        # Write the connection file
        kernel_manager.write_connection_file()

        # Launch RPC thread
        # NOTE: This is delayed for so long to be able to "catch" the connection info
        # TODO: LOW, Reduce the use of global variables in RpcServerThread
        rpc_serv = RpcServerThread(connection_info=kernel_manager.connection_file)
        rpc_serv.start()

        # Start the event loop
        # This starts the console and blocks until the user closes the window of the application.
        guisupport.start_event_loop_qt4(app)
        # Application is shutting down.
        # Stop the RPC "bridge"
        # The rpyc ThreadedServer is "closed", this causes .start() in the thread's run()  to return, effectively
        # unblocking (and terminating) the thread.
        rpc_serv.stop_server()
        # Stop the client
        kernel_client.stop_channels()
        # Shutdown the kernel
        kernel_manager.shutdown_kernel()


if __name__ == "__main__":
    if yasara.request == "CheckIfDisabled":
        yasara.plugin.exitcode = yapycon_plugin_check_if_disabled()
    else:
        yapycon_launch_plugin(yasara.request)
    yasara.plugin.end()
