"""Custom ZHA Quirk for Shelly 1 Gen4 to expose the detached input as a binary sensor."""

from typing import Any

from zigpy.quirks import CustomCluster
from zigpy.quirks.v2 import QuirkBuilder
from zigpy.types import Addressing
from zigpy.zcl import ClusterType, foundation
from zigpy.zcl.clusters.general import OnOff


class ShellyInputOnOffClientCluster(CustomCluster, OnOff):
    """Shelly detached input OnOff client cluster that updates on_off state on command."""

    def handle_cluster_request(
        self,
        hdr: foundation.ZCLHeader,
        args: list[Any],
        *,
        dst_addressing: Addressing.Group
        | Addressing.IEEE
        | Addressing.NWK
        | None = None,
    ) -> None:
        """Update the on_off attribute when On/Off/Toggle client commands are received."""
        if hdr.command_id in (
            OnOff.ServerCommandDefs.off.id,
            OnOff.ServerCommandDefs.off_with_effect.id,
        ):
            self._update_attribute(OnOff.AttributeDefs.on_off.id, False)
        elif hdr.command_id in (
            OnOff.ServerCommandDefs.on.id,
            OnOff.ServerCommandDefs.on_with_recall_global_scene.id,
            OnOff.ServerCommandDefs.on_with_timed_off.id,
        ):
            self._update_attribute(OnOff.AttributeDefs.on_off.id, True)
        elif hdr.command_id == OnOff.ServerCommandDefs.toggle.id:
            current = self.get(OnOff.AttributeDefs.on_off.id)
            self._update_attribute(OnOff.AttributeDefs.on_off.id, not bool(current))

        super().handle_cluster_request(hdr, args, dst_addressing=dst_addressing)


quirk = (
    QuirkBuilder("Shelly", "1")
    .replaces(
        ShellyInputOnOffClientCluster,
        endpoint_id=2,
        cluster_type=ClusterType.Client,
    )
    .binary_sensor(
        OnOff.AttributeDefs.on_off.name,
        OnOff.cluster_id,
        endpoint_id=2,
        cluster_type=ClusterType.Client,
        translation_key="input",
        fallback_name="Input",
    )
)

try:
    from zhaquirks.shelly import (
        SHELLY_WIFI_SETUP_ENDPOINT_ID,
        ShellyCustomProfileDevice,
        ShellyWiFiSetupCluster,
    )

    quirk = quirk.device_class(ShellyCustomProfileDevice).replaces(
        ShellyWiFiSetupCluster, endpoint_id=SHELLY_WIFI_SETUP_ENDPOINT_ID
    )
except ImportError:
    pass

quirk.add_to_registry()
