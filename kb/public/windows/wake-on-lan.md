---
topic: windows/wake-on-lan
priority: P3
applies_to: "Wake-on-LAN for managed Windows devices: BIOS/UEFI, network adapter, Configuration Manager, Intune DFCI, Surface (docs updated 2026-02 to 2026-08)"
retrieved_utc: 2026-11-09
sources: [S-htaqvpiw, S-nf2pxtta, S-jnot3jwd, S-ma44wwsm, S-sz3xwsns]
status: partial
---

# Wake-on-LAN for managed devices

## Summary
- Waking a sleeping managed PC needs three layers: the firmware (BIOS/UEFI) must allow wake from LAN, the network adapter must be set to wake the computer on a magic packet, and a sender (Configuration Manager, or any tool) must send the packet.
- The BIOS menu names are vendor specific and not documented by Microsoft in general; the documented Microsoft routes are the Intune DFCI profile (Surface and DFCI-capable devices) and, for Surface, the dock and adapter rules.
- Configuration Manager 1810 and later sets the adapter's wake option through the **Allow network wake-up** client setting.

## Facts
- Wake on LAN lets the network adapter keep listening while the computer is in a power-saving state and wake it when a special packet arrives; Windows 7 and Vista leave it disabled by default. [DOC S-jnot3jwd]
- To avoid unwanted wake-ups the Windows 7 and Vista article recommends allowing only a Magic Packet to wake the computer (adapter **Properties > Configure > Power Management**: "Allow this device to wake the computer" and "Only allow a magic packet to wake the computer"); a Magic Packet targets one adapter's MAC address. [DOC S-jnot3jwd]
- The same article adds that you may also have to enable BIOS settings for WOL, and which settings depends on the computer's manufacturer. [DOC S-jnot3jwd]
- Configuration Manager's planning page says network adapters, and possibly the BIOS, must be enabled and configured for wake-up packets; if the adapter is not configured, Configuration Manager configures it when it receives the client setting to enable wake-up proxy. [DOC S-nf2pxtta]
- Intune's DFCI profile (Windows) has a **Wake on LAN** setting: Not configured (Intune changes nothing; the OS might prevent wake), Enabled (UEFI/BIOS allows waking by LAN) or Disabled (UEFI/BIOS prevents it); a sibling **Wake on power** setting works the same way for power-source wake. [DOC S-ma44wwsm]
- Configuration Manager 1810 and later: before, clients had to be enabled in the network adapter properties by hand; the client setting **Allow network wake-up** (Power Management client settings, **Administration > Client Settings**) replaces that. [DOC S-htaqvpiw]
- Since 1810 the site can wake clients from the console through client notification (right-click a device or a device collection, **Client Notification > Wake up**): the site server uses clients awake on the same remote subnet to send the magic packet; only sleeping clients are sent a request; built-in collections cannot be used. [DOC S-htaqvpiw]
- Limits of the 1810 method: at least one client in the target subnet must be awake; IPv6 and 802.1x network authentication are not supported (802.1x may work with extra configuration); DHCP leases must not be infinite. [DOC S-htaqvpiw]
- Since 2010 a required deployment with a deadline and **Send wake-up packages** enabled can wake devices through the client notification channel, if the site's **Wake on LAN** tab uses the client notification channel and **Allow network wake-up** is enabled. [DOC S-htaqvpiw]
- Since 1902 the **Wake On LAN port number (UDP)** client setting is honoured by both the new and the older method. [DOC S-htaqvpiw]
- The console's Wake Up action needs the **Notify resource** permission on the Collection category. [DOC S-htaqvpiw]
- Wake-up proxy (older method) limits: guest operating systems on virtual machines are unsupported, 802.1X networks are unsupported, and the traffic is unencrypted and unauthenticated; it can cause MAC flaps that monitoring tools may alert on. [DOC S-nf2pxtta]
- Surface devices wake from Modern Standby by default on Windows 10 1607 or later with no IT configuration (Surface Studio 2 excepted), when plugged into AC and wired through a Surface Ethernet adapter or dock. [DOC S-sz3xwsns]
- A magic packet carries the target NIC's MAC address; the NIC compares it with its own before waking the device. [DOC S-sz3xwsns]
- How it fits (laptops): wake from hibernation or shutdown needs the firmware option on, so for a mixed laptop fleet check the vendor's BIOS setting by model; Microsoft's own firmware route is DFCI, which needs devices that support it. [DER S-jnot3jwd, S-ma44wwsm: BIOS dependence stated; DFCI setting from its reference]
- The BIOS menu name and path for non-Surface vendors (for example "Wake on LAN" under Power Management) is vendor documentation and was not read; the kb has no vendor source. [UNK]

## Reference
| Layer | Setting | Source |
|---|---|---|
| Firmware | vendor BIOS/UEFI option, or Intune DFCI **Wake on LAN** Enabled | S-jnot3jwd, S-ma44wwsm |
| Adapter | "Allow this device to wake the computer" and "Only allow a magic packet..." | S-jnot3jwd |
| Configuration Manager | client setting **Allow network wake-up**, site **Wake on LAN** tab | S-htaqvpiw |

## Examples
- None.
