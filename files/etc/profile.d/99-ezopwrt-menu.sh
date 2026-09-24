#!/bin/sh
# EzOpWrt console shortcut menu (restored from the original 1lin.img)
# The original image appended "/usr/bin/zsh" to /etc/profile and put the menu
# in /etc/profiles, launched from /root/.zshrc.  We can skip the zsh layer and
# run the very same /etc/profiles script directly with bash.

[ -n "$PS1" ] || return 0            # interactive (login) shells only
[ -f /etc/profiles ] || return 0
[ -x /bin/bash ] || return 0
[ -n "$EZOPWRT_MENU_RUNNING" ] && return 0

echo ""
if command -v EG >/dev/null 2>&1; then
	EG " menu->调用菜单(Call Menu) 进阶设置可禁用/显示SSH登陆菜单 "
else
	echo -e "\e[32m menu->调用菜单(Call Menu) 进阶设置可禁用/显示SSH登陆菜单 \e[0m"
fi
echo ""

export EZOPWRT_MENU_RUNNING=1
/bin/bash /etc/profiles
unset EZOPWRT_MENU_RUNNING