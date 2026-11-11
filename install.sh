#!/bin/bash
# Hook de instalación del plugin para aaPanel (instalar/actualizar/desinstalar el PLUGIN).
# El runtime de ChromaDB se instala desde la interfaz del plugin (scripts/setup.sh).
PATH=/www/server/panel/pyenv/bin:/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin
export PATH
install_tmp='/tmp/bt_install.pl'
pluginPath=/www/server/panel/plugin/chromadb

Install_chromadb()
{
    mkdir -p $pluginPath
    chmod 700 $pluginPath
    chmod 600 $pluginPath/*.py $pluginPath/*.json 2>/dev/null
    chmod 700 $pluginPath/scripts/*.sh 2>/dev/null
    \cp -a $pluginPath/icon.png /www/server/panel/BTPanel/static/img/soft_ico/ico-chromadb.png 2>/dev/null
    echo 'The installation is complete' > $install_tmp
}

Uninstall_chromadb()
{
    # Quita el runtime pero conserva los datos en /www/server/chromadb/data
    bash $pluginPath/scripts/remove.sh 2>/dev/null
    rm -f /www/server/panel/vhost/nginx/chromadb_remote.conf
    /etc/init.d/nginx reload >/dev/null 2>&1
    rm -f /www/server/panel/BTPanel/static/img/soft_ico/ico-chromadb.png
    rm -rf $pluginPath
}

if [ "${1}" == 'install' ] || [ "${1}" == 'update' ]; then
    Install_chromadb
elif [ "${1}" == 'uninstall' ]; then
    Uninstall_chromadb
fi
