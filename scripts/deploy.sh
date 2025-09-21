#!/bin/bash

# FluentGO Deployment Script
# Автоматическое развертывание с проверками

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка зависимостей
check_dependencies() {
    print_info "Проверка зависимостей..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker не установлен!"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose не установлен!"
        exit 1
    fi
    
    print_success "Все зависимости установлены"
}

# Проверка .env файла
check_env_file() {
    print_info "Проверка файла .env..."
    
    if [ ! -f ".env" ]; then
        print_warning ".env файл не найден, создаю из шаблона..."
        cp env.example .env
        print_error "Заполните .env файл и запустите скрипт снова!"
        exit 1
    fi
    
    # Проверка обязательных переменных
    required_vars=("OPENAI_API_KEY" "ELEVENLABS_API_KEY" "JWT_secret")
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" .env || grep -q "^${var}=.*your_.*_here" .env; then
            print_error "Переменная ${var} не заполнена в .env файле!"
            exit 1
        fi
    done
    
    print_success "Файл .env корректно настроен"
}

# Создание необходимых директорий
create_directories() {
    print_info "Создание необходимых директорий..."
    
    mkdir -p temp
    mkdir -p ssl
    mkdir -p backups
    mkdir -p logs
    
    # Создание пустой базы данных если не существует
    if [ ! -f "users.db" ]; then
        touch users.db
        print_info "Создан пустой файл базы данных"
    fi
    
    print_success "Директории созданы"
}

# Остановка существующих контейнеров
stop_existing() {
    print_info "Остановка существующих контейнеров..."
    
    if docker-compose ps -q | grep -q .; then
        docker-compose down
        print_success "Контейнеры остановлены"
    else
        print_info "Активных контейнеров не найдено"
    fi
}

# Сборка и запуск
build_and_start() {
    print_info "Сборка и запуск контейнеров..."
    
    # Определяем какой compose файл использовать
    if [ "$1" = "prod" ]; then
        COMPOSE_FILE="docker-compose.prod.yml"
        print_info "Используется продакшен конфигурация"
    else
        COMPOSE_FILE="docker-compose.yml"
        print_info "Используется dev конфигурация"
    fi
    
    # Сборка образов
    docker-compose -f $COMPOSE_FILE build --no-cache
    
    # Запуск сервисов
    docker-compose -f $COMPOSE_FILE up -d
    
    print_success "Контейнеры запущены"
}

# Проверка здоровья сервисов
check_health() {
    print_info "Проверка здоровья сервисов..."
    
    # Ждем запуска сервисов
    sleep 30
    
    # Проверка API
    if curl -f -s http://localhost/api/test-db > /dev/null; then
        print_success "API работает корректно"
    else
        print_error "API не отвечает!"
        docker-compose logs app
        exit 1
    fi
    
    # Проверка Nginx
    if curl -f -s http://localhost/health > /dev/null; then
        print_success "Nginx работает корректно"
    else
        print_warning "Nginx health check не прошел"
    fi
}

# Создание бэкапа
create_backup() {
    if [ -f "users.db" ] && [ -s "users.db" ]; then
        backup_name="backup_$(date +%Y%m%d_%H%M%S).db"
        cp users.db "backups/$backup_name"
        print_success "Создан бэкап: $backup_name"
    fi
}

# Показ статуса
show_status() {
    print_info "Статус сервисов:"
    docker-compose ps
    
    print_info "\nИспользование ресурсов:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
    
    print_info "\nДоступные endpoints:"
    echo "  - Веб-интерфейс: http://localhost"
    echo "  - API: http://localhost/api/"
    echo "  - Health check: http://localhost/health"
    echo "  - WebSocket VAD: ws://localhost/ws"
    echo "  - WebSocket Button: ws://localhost/ws-button"
}

# Главная функция
main() {
    echo "🚀 FluentGO Deployment Script"
    echo "=============================="
    
    # Проверки
    check_dependencies
    check_env_file
    
    # Создание бэкапа перед развертыванием
    create_backup
    
    # Подготовка
    create_directories
    stop_existing
    
    # Развертывание
    build_and_start $1
    
    # Проверка
    check_health
    show_status
    
    print_success "🎉 Развертывание завершено успешно!"
    print_info "Откройте http://localhost в браузере"
}

# Обработка аргументов
case "$1" in
    "prod")
        main prod
        ;;
    "dev"|"")
        main dev
        ;;
    "stop")
        print_info "Остановка всех сервисов..."
        docker-compose down
        print_success "Сервисы остановлены"
        ;;
    "restart")
        print_info "Перезапуск сервисов..."
        docker-compose restart
        print_success "Сервисы перезапущены"
        ;;
    "logs")
        docker-compose logs -f
        ;;
    "status")
        show_status
        ;;
    "backup")
        create_backup
        ;;
    *)
        echo "Использование: $0 [dev|prod|stop|restart|logs|status|backup]"
        echo ""
        echo "Команды:"
        echo "  dev      - Запуск в режиме разработки (по умолчанию)"
        echo "  prod     - Запуск в продакшен режиме"
        echo "  stop     - Остановка всех сервисов"
        echo "  restart  - Перезапуск сервисов"
        echo "  logs     - Просмотр логов"
        echo "  status   - Показать статус сервисов"
        echo "  backup   - Создать бэкап базы данных"
        exit 1
        ;;
esac
