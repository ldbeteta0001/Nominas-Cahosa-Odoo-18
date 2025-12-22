#!/bin/bash

# Script para crear repositorio "Nomina Cahosa Odoo 18" en GitHub
# Uso: ./crear_repo_github.sh TU_TOKEN_AQUI

REPO_NAME="Nomina-Cahosa-Odoo-18"
DESCRIPTION="Módulo de Nómina para Odoo 18 - Cahosa"
GITHUB_USER="luisd.beteta10"

if [ -z "$1" ]; then
    echo "❌ Error: Necesitas proporcionar un token de GitHub"
    echo "Uso: $0 TU_TOKEN_DE_GITHUB"
    echo ""
    echo "Para obtener un token:"
    echo "1. Ve a: https://github.com/settings/tokens"
    echo "2. Click en 'Generate new token' -> 'Generate new token (classic)'"
    echo "3. Selecciona scopes: repo, read:org, gist"
    echo "4. Copia el token generado"
    exit 1
fi

TOKEN=$1

echo "🚀 Creando repositorio '$REPO_NAME' en GitHub..."

# Crear repositorio en GitHub
RESPONSE=$(curl -s -X POST \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/user/repos \
  -d "{\"name\":\"$REPO_NAME\",\"description\":\"$DESCRIPTION\",\"private\":false}")

# Verificar si se creó correctamente
if echo "$RESPONSE" | grep -q "Bad credentials"; then
    echo "❌ Error: Token inválido. Verifica tu token de GitHub."
    exit 1
elif echo "$RESPONSE" | grep -q "name already exists"; then
    echo "⚠️  El repositorio ya existe. Continuando..."
    REPO_URL="https://github.com/$GITHUB_USER/$REPO_NAME.git"
elif echo "$RESPONSE" | grep -q "\"id\""; then
    echo "✅ Repositorio creado exitosamente!"
    REPO_URL="https://github.com/$GITHUB_USER/$REPO_NAME.git"
else
    echo "❌ Error al crear el repositorio:"
    echo "$RESPONSE"
    exit 1
fi

echo ""
echo "📋 Configurando remoto 'github'..."

# Configurar nuevo remoto o actualizar existente
cd /opt/odoo/addons/kc_payroll_full

if git remote | grep -q "^github$"; then
    git remote set-url github "$REPO_URL"
    echo "✅ Remoto 'github' actualizado"
else
    git remote add github "$REPO_URL"
    echo "✅ Remoto 'github' agregado"
fi

echo ""
echo "✅ ¡Listo! El repositorio está configurado."
echo ""
echo "Para hacer push de tu código:"
echo "  git add ."
echo "  git commit -m 'Tu mensaje'"
echo "  git push github main"
echo ""
echo "O si quieres cambiar el remoto 'origin':"
echo "  git remote set-url origin $REPO_URL"

