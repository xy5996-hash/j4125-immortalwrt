# SPDX-License-Identifier: GPL-3.0-only

include $(TOPDIR)/rules.mk

PKG_NAME:=mihomo-core
PKG_VERSION:=1.19.31
PKG_RELEASE:=1

PKG_LICENSE:=GPL-3.0-only
PKG_MAINTAINER:=xy5996-hash

PKG_SOURCE:=mihomo-linux-amd64-compatible-v$(PKG_VERSION).gz
PKG_SOURCE_URL:=https://github.com/MetaCubeX/mihomo/releases/download/v$(PKG_VERSION)
PKG_HASH:=04cf9f09671704f839ddbee2e93069dc831a4123a75281e725d1d96ab9ac1afc
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(PKG_VERSION)
PKGARCH:=x86_64

include $(INCLUDE_DIR)/package.mk

define Package/mihomo-core
  SECTION:=net
  CATEGORY:=Network
  TITLE:=mihomo core for OpenClash
  URL:=https://github.com/MetaCubeX/mihomo
  PKGARCH:=x86_64
endef

define Package/mihomo-core/description
  Pinned mihomo core installed as /etc/openclash/core/clash_meta.
endef

define Build/Prepare
	$(INSTALL_DIR) $(PKG_BUILD_DIR)
	gzip -dc $(DL_DIR)/$(PKG_SOURCE) > $(PKG_BUILD_DIR)/clash_meta
	chmod 0755 $(PKG_BUILD_DIR)/clash_meta
endef

define Build/Configure
endef

define Build/Compile
endef

define Package/mihomo-core/install
	$(INSTALL_DIR) $(1)/etc/openclash/core
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/clash_meta $(1)/etc/openclash/core/clash_meta
endef

$(eval $(call BuildPackage,mihomo-core))