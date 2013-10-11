DESCRIPTION = "enigma2 iptv plugin for KartinaTV & RodnoeTV"
MAINTAINER = "Alex Maystrenko <alexeytech@gmail.com>"
HOMEPAGE = "http://code.google.com/p/kartinatv-dm/"
LICENSE = "GNU GPLv2"
SECTION = "extra"
LIC_FILES_CHKSUM = "file://${FILE_DIRNAME}/build/COPYING;md5=d41d8cd98f00b204e9800998ecf8427e"

PN="enigma2-plugin-extensions-iptvdream"

PV="2.4.1"
VVV = "r0"
PR = "${VVV}"

SRC_URI = "file://${FILE_DIRNAME}/build"
S = "${WORKDIR}/build"

EXTRA_OECONF = " \
        BUILD_SYS=${BUILD_SYS} \
        HOST_SYS=${HOST_SYS} \
        STAGING_INCDIR=${STAGING_INCDIR} \
        STAGING_LIBDIR=${STAGING_LIBDIR} \
"
EXTRA_OECONF += " --with-po "

FILES_${PN} += " /usr/share/enigma2/iptvdream_skin /usr/lib/enigma2/python/Plugins/Extensions/iptvDream /etc"

FILES_${PN}-dbg = " /usr/lib/enigma2/python/Plugins/Extensions/iptvDream/.debug "

DEPENDS = "enigma2"

inherit autotools

pkg_postinst() {
	#!/bin/sh
	mkdir -p /etc/iptvdream/
	F="/etc/iptvdream/playlist.m3u"
	if ! test -f $F; then
		echo """#EXTM3U
#EXTINF:0,example stream
rtsp://82.177.67.61/axis-media/media.amp
""" > $F
	fi
}
