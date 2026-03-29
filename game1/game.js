// ============================================
// 🚀 ГАЛАКТИЧЕСКАЯ ИМПЕРИЯ - Игровая Логика
// ============================================

// Игровые данные
const gameState = {
    resources: {
        fuel: 100,
        minerals: 0,
        crystals: 0,
        energy: 50,
        credits: 500
    },
    ship: {
        maxFuel: 100,
        maxEnergy: 50,
        maxCargo: 100,
        currentCargo: 0,
        health: 100
    },
    empire: {
        level: 1,
        systems: 1,
        factories: 0,
        mines: 0,
        stations: 0,
        days: 1
    },
    currentSystem: 0,
    selectedSystem: null
};

// Звёздные системы
const starSystems = [
    { id: 0, name: "Солнечная Система", type: "Столица", x: 400, y: 300, resources: { minerals: 5, crystals: 2, energy: 10 }, distance: 0, owned: true },
    { id: 1, name: "Альфа Центавра", type: "Звёздная Система", x: 200, y: 200, resources: { minerals: 8, crystals: 5, energy: 7 }, distance: 150, owned: false },
    { id: 2, name: "Проксима", type: "Красный Карлик", x: 600, y: 200, resources: { minerals: 6, crystals: 3, energy: 8 }, distance: 200, owned: false },
    { id: 3, name: "Сириус", type: "Голубой Гигант", x: 300, y: 450, resources: { minerals: 10, crystals: 8, energy: 12 }, distance: 250, owned: false },
    { id: 4, name: "Вега", type: "Белая Звезда", x: 500, y: 450, resources: { minerals: 7, crystals: 10, energy: 9 }, distance: 300, owned: false },
    { id: 5, name: "Туманность Ориона", type: "Туманность", x: 150, y: 400, resources: { minerals: 15, crystals: 12, energy: 15 }, distance: 350, owned: false },
    { id: 6, name: "Андромеда", type: "Галактика", x: 650, y: 350, resources: { minerals: 20, crystals: 15, energy: 20 }, distance: 400, owned: false }
];

// Цены на ресурсы
const resourcePrices = {
    minerals: { buy: 10, sell: 8 },
    crystals: { buy: 25, sell: 20 },
    energy: { buy: 5, sell: 4 }
};

// ============================================
// ИНИЦИАЛИЗАЦИЯ
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    initCanvas();
    updateUI();
    setupEventListeners();
    logMessage("🎮 Добро пожаловать в Галактическую Империю!");
    logMessage("🚀 Ваша миссия: захватить как можно больше систем!");
});

// ============================================
// CANVAS - ОТРИСОВКА КАРТЫ
// ============================================

let canvas, ctx;

function initCanvas() {
    canvas = document.getElementById('galaxy-canvas');
    ctx = canvas.getContext('2d');
    drawGalaxyMap();
}

function drawGalaxyMap() {
    // Очистка
    ctx.fillStyle = '#0a0a2e';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Рисуем звёзды
    drawStars();
    
    // Рисуем связи между системами
    drawConnections();
    
    // Рисуем системы
    starSystems.forEach(system => {
        drawSystem(system);
    });
    
    // Рисуем корабль
    drawShip();
}

function drawStars() {
    ctx.fillStyle = '#ffffff';
    for (let i = 0; i < 100; i++) {
        const x = Math.random() * canvas.width;
        const y = Math.random() * canvas.height;
        const size = Math.random() * 2;
        const opacity = Math.random() * 0.5 + 0.3;
        ctx.globalAlpha = opacity;
        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.globalAlpha = 1;
}

function drawConnections() {
    ctx.strokeStyle = 'rgba(74, 158, 255, 0.3)';
    ctx.lineWidth = 2;
    
    for (let i = 0; i < starSystems.length; i++) {
        for (let j = i + 1; j < starSystems.length; j++) {
            const sys1 = starSystems[i];
            const sys2 = starSystems[j];
            const dist = Math.sqrt(Math.pow(sys2.x - sys1.x, 2) + Math.pow(sys2.y - sys1.y, 2));
            
            if (dist < 300) {
                ctx.beginPath();
                ctx.moveTo(sys1.x, sys1.y);
                ctx.lineTo(sys2.x, sys2.y);
                ctx.stroke();
            }
        }
    }
}

function drawSystem(system) {
    const isSelected = gameState.selectedSystem === system.id;
    const isOwned = system.owned;
    const isCurrent = gameState.currentSystem === system.id;
    
    // Свечение
    const gradient = ctx.createRadialGradient(system.x, system.y, 0, system.x, system.y, 30);
    if (isCurrent) {
        gradient.addColorStop(0, 'rgba(74, 158, 255, 0.8)');
        gradient.addColorStop(1, 'rgba(74, 158, 255, 0)');
    } else if (isOwned) {
        gradient.addColorStop(0, 'rgba(0, 255, 100, 0.6)');
        gradient.addColorStop(1, 'rgba(0, 255, 100, 0)');
    } else {
        gradient.addColorStop(0, 'rgba(255, 200, 50, 0.4)');
        gradient.addColorStop(1, 'rgba(255, 200, 50, 0)');
    }
    
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(system.x, system.y, 30, 0, Math.PI * 2);
    ctx.fill();
    
    // Основная точка
    ctx.beginPath();
    ctx.arc(system.x, system.y, isCurrent ? 12 : 8, 0, Math.PI * 2);
    ctx.fillStyle = isCurrent ? '#4a9eff' : (isOwned ? '#00ff64' : '#ffc832');
    ctx.fill();
    
    // Обводка
    ctx.strokeStyle = isSelected ? '#ffffff' : '#4a9eff';
    ctx.lineWidth = isSelected ? 3 : 2;
    ctx.stroke();
    
    // Название
    ctx.fillStyle = '#ffffff';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(system.name, system.x, system.y + 45);
    
    // Тип
    ctx.fillStyle = '#aaaaaa';
    ctx.font = '10px Arial';
    ctx.fillText(system.type, system.x, system.y + 58);
}

function drawShip() {
    const currentSys = starSystems.find(s => s.id === gameState.currentSystem);
    if (currentSys) {
        ctx.fillStyle = '#4a9eff';
        ctx.font = '20px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('🚀', currentSys.x, currentSys.y - 20);
    }
}

// ============================================
// ОБНОВЛЕНИЕ ИНТЕРФЕЙСА
// ============================================

function updateUI() {
    // Ресурсы
    document.querySelector('#fuel .value').textContent = Math.floor(gameState.resources.fuel);
    document.querySelector('#minerals .value').textContent = Math.floor(gameState.resources.minerals);
    document.querySelector('#crystals .value').textContent = Math.floor(gameState.resources.crystals);
    document.querySelector('#energy .value').textContent = Math.floor(gameState.resources.energy);
    document.querySelector('#credits .value').textContent = Math.floor(gameState.resources.credits);
    
    // Прогресс бары
    document.getElementById('fuel-bar').style.width = `${(gameState.resources.fuel / gameState.ship.maxFuel) * 100}%`;
    document.getElementById('energy-bar').style.width = `${(gameState.resources.energy / gameState.ship.maxEnergy) * 100}%`;
    
    // Груз
    document.getElementById('cargo').textContent = `${gameState.ship.currentCargo}/${gameState.ship.maxCargo}`;
    
    // Статистика
    document.getElementById('stat-systems').textContent = gameState.empire.systems;
    document.getElementById('stat-factories').textContent = gameState.empire.factories;
    document.getElementById('stat-days').textContent = gameState.empire.days;
    document.getElementById('empire-level').textContent = `Уровень ${gameState.empire.level}`;
    
    // Кнопки
    document.getElementById('btn-refuel').disabled = gameState.resources.credits < 50;
    document.getElementById('btn-repair').disabled = gameState.resources.credits < 100;
    document.getElementById('btn-build-mine').disabled = gameState.resources.credits < 200;
    document.getElementById('btn-build-factory').disabled = gameState.resources.credits < 500;
    document.getElementById('btn-build-station').disabled = gameState.resources.credits < 1000;
    
    // Перерисовка карты
    drawGalaxyMap();
}

// ============================================
// ОБРАБОТЧИКИ СОБЫТИЙ
// ============================================

function setupEventListeners() {
    // Клик по карте
    canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        // Проверка клика по системе
        starSystems.forEach(system => {
            const dist = Math.sqrt(Math.pow(x - system.x, 2) + Math.pow(y - system.y, 2));
            if (dist < 20) {
                selectSystem(system);
            }
        });
    });
    
    // Кнопки корабля
    document.getElementById('btn-refuel').addEventListener('click', refuel);
    document.getElementById('btn-repair').addEventListener('click', repair);
    
    // Кнопки строительства
    document.getElementById('btn-build-mine').addEventListener('click', buildMine);
    document.getElementById('btn-build-factory').addEventListener('click', buildFactory);
    document.getElementById('btn-build-station').addEventListener('click', buildStation);
    
    // Торговля
    document.getElementById('btn-sell').addEventListener('click', sellResource);
    document.getElementById('btn-buy').addEventListener('click', buyResource);
    
    // Путешествие
    document.getElementById('btn-travel').addEventListener('click', travel);
    
    // Модальное окно
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('modal-overlay').addEventListener('click', (e) => {
        if (e.target.id === 'modal-overlay') closeModal();
    });
}

// ============================================
// ИГРОВЫЕ ДЕЙСТВИЯ
// ============================================

function selectSystem(system) {
    gameState.selectedSystem = system.id;
    
    document.getElementById('system-name').textContent = system.name;
    document.getElementById('system-type').textContent = `Тип: ${system.type}`;
    document.getElementById('system-resources').textContent = 
        `Ресурсы: 🪨${system.resources.minerals} 💎${system.resources.crystals} ⚡${system.resources.energy}`;
    document.getElementById('system-distance').textContent = `Расстояние: ${system.distance} св.лет`;
    
    const travelBtn = document.getElementById('btn-travel');
    if (system.id === gameState.currentSystem) {
        travelBtn.disabled = true;
        travelBtn.textContent = "Вы здесь";
    } else if (gameState.resources.fuel < system.distance) {
        travelBtn.disabled = true;
        travelBtn.textContent = "Недостаточно топлива";
    } else {
        travelBtn.disabled = false;
        travelBtn.textContent = system.owned ? "Переместиться" : "Захватить";
    }
    
    updateUI();
}

function travel() {
    const targetSystem = starSystems.find(s => s.id === gameState.selectedSystem);
    if (!targetSystem) return;
    
    const fuelCost = targetSystem.distance;
    if (gameState.resources.fuel < fuelCost) {
        showModal("⛽ Недостаточно топлива!", "Заправьтесь перед путешествием.");
        return;
    }
    
    gameState.resources.fuel -= fuelCost;
    gameState.currentSystem = targetSystem.id;
    
    if (!targetSystem.owned) {
        targetSystem.owned = true;
        gameState.empire.systems++;
        logMessage(`🎉 Захвачена система: ${targetSystem.name}!`);
    } else {
        logMessage(`🚀 Перемещение в ${targetSystem.name}`);
    }
    
    gameState.empire.days++;
    checkLevelUp();
    updateUI();
}

function refuel() {
    if (gameState.resources.credits >= 50) {
        gameState.resources.credits -= 50;
        gameState.resources.fuel = gameState.ship.maxFuel;
        logMessage("⛽ Корабль заправлен!");
        updateUI();
    }
}

function repair() {
    if (gameState.resources.credits >= 100) {
        gameState.resources.credits -= 100;
        gameState.ship.health = 100;
        logMessage("🔧 Корабль отремонтирован!");
        updateUI();
    }
}

function buildMine() {
    if (gameState.resources.credits >= 200) {
        gameState.resources.credits -= 200;
        gameState.empire.mines++;
        gameState.empire.days++;
        logMessage("🏭 Построена шахта! +5 минералов/день");
        updateUI();
    }
}

function buildFactory() {
    if (gameState.resources.credits >= 500) {
        gameState.resources.credits -= 500;
        gameState.empire.factories++;
        gameState.empire.days++;
        logMessage("🏭 Построен завод! +10 энергии/день");
        updateUI();
    }
}

function buildStation() {
    if (gameState.resources.credits >= 1000) {
        gameState.resources.credits -= 1000;
        gameState.empire.stations++;
        gameState.empire.days++;
        logMessage("🛰️ Построена станция! +5 кристаллов/день");
        updateUI();
    }
}

function sellResource() {
    const resource = document.getElementById('trade-resource').value;
    const amount = 10;
    const price = resourcePrices[resource].sell;
    
    if (gameState.resources[resource] >= amount) {
        gameState.resources[resource] -= amount;
        gameState.resources.credits += amount * price;
        logMessage(`💱 Продано ${amount} ${resource} за ${amount * price}💰`);
        updateUI();
    } else {
        showModal("⚠️ Недостаточно ресурсов", "У вас нет enough ресурсов для продажи.");
    }
}

function buyResource() {
    const resource = document.getElementById('trade-resource').value;
    const amount = 10;
    const price = resourcePrices[resource].buy;
    const totalCost = amount * price;
    
    if (gameState.resources.credits >= totalCost) {
        gameState.resources.credits -= totalCost;
        gameState.resources[resource] += amount;
        logMessage(`💱 Куплено ${amount} ${resource} за ${totalCost}💰`);
        updateUI();
    } else {
        showModal("💰 Недостаточно кредитов", "У вас нет enough кредитов для покупки.");
    }
}

function checkLevelUp() {
    const newLevel = Math.floor(gameState.empire.systems / 2) + 1;
    if (newLevel > gameState.empire.level) {
        gameState.empire.level = newLevel;
        showModal("🎉 ПОВЫШЕНИЕ УРОВНЯ!", `Ваш уровень империи: ${newLevel}`);
        logMessage(`⭐ Уровень повышен до ${newLevel}!`);
    }
    
    // Пассивный доход
    gameState.resources.minerals += gameState.empire.mines * 5;
    gameState.resources.energy += gameState.empire.factories * 10;
    gameState.resources.crystals += gameState.empire.stations * 5;
}

// ============================================
// УТИЛИТЫ
// ============================================

function logMessage(message) {
    const log = document.getElementById('message-log');
    const msg = document.createElement('p');
    msg.className = 'message';
    msg.textContent = `[День ${gameState.empire.days}] ${message}`;
    log.insertBefore(msg, log.firstChild);
    
    // Ограничиваем количество сообщений
    while (log.children.length > 20) {
        log.removeChild(log.lastChild);
    }
}

function showModal(title, message) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-message').textContent = message;
    document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.add('hidden');
}

// Игровой цикл (пассивный доход каждые 10 секунд)
setInterval(() => {
    if (gameState.empire.mines > 0 || gameState.empire.factories > 0 || gameState.empire.stations > 0) {
        gameState.resources.minerals += gameState.empire.mines * 2;
        gameState.resources.energy += gameState.empire.factories * 3;
        gameState.resources.crystals += gameState.empire.stations * 1;
        updateUI();
    }
}, 10000);