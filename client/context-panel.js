/**
 * Context Panel Renderer
 * Updates the right-side panel with player stats, party, map, and inventory
 */

(function() {
  const ContextPanel = {
    container: null,
    
    init() {
      this.container = document.getElementById('context-panel');
      if (!this.container) {
        console.error('Context panel container not found');
        return;
      }
      this.renderEmpty();
    },
    
    renderEmpty() {
      this.container.innerHTML = `
        <div class="context-section">
          <div class="context-section-title">Player</div>
          <div style="color: #555; font-size: 11px; font-style: italic;">
            Loading...
          </div>
        </div>
      `;
    },
    
    update(data) {
      if (!this.container || !data) return;
      
      const html = `
        ${this.renderPlayer(data.player)}
        ${this.renderParty(data.party)}
        ${this.renderMap(data.map)}
        ${this.renderEnvironment(data.environment)}
        ${this.renderInventory(data.inventory)}
      `;
      
      this.container.innerHTML = html;
    },
    
    renderPlayer(player) {
      if (!player) return '';
      
      const hpPct = Math.round((player.hp / player.max_hp) * 100);
      const mpPct = Math.round((player.mp / player.max_mp) * 100);
      
      const hungerClass = player.hunger > 70 ? 'good' : player.hunger > 30 ? 'warning' : 'critical';
      const thirstClass = player.thirst > 70 ? 'good' : player.thirst > 30 ? 'warning' : 'critical';
      const staminaClass = player.stamina > 70 ? 'good' : player.stamina > 30 ? 'warning' : 'critical';
      
      return `
        <div class="context-section">
          <div class="context-section-title">Character</div>
          
          <div class="player-header">
            <span class="player-name">${player.name}</span>
            <span class="player-class">Lv${player.level} ${player.class}</span>
          </div>
          
          <div class="resource-bar">
            <div class="resource-label">
              <span>HP</span>
              <span>${player.hp}/${player.max_hp}</span>
            </div>
            <div class="resource-track">
              <div class="resource-fill hp-fill" style="width: ${hpPct}%"></div>
            </div>
          </div>
          
          <div class="resource-bar">
            <div class="resource-label">
              <span>MP</span>
              <span>${player.mp}/${player.max_mp}</span>
            </div>
            <div class="resource-track">
              <div class="resource-fill mp-fill" style="width: ${mpPct}%"></div>
            </div>
          </div>
          
          <div class="survival-stats">
            <div class="survival-stat">
              <div class="survival-label">Hunger</div>
              <div class="survival-value ${hungerClass}">${player.hunger}%</div>
            </div>
            <div class="survival-stat">
              <div class="survival-label">Thirst</div>
              <div class="survival-value ${thirstClass}">${player.thirst}%</div>
            </div>
            <div class="survival-stat">
              <div class="survival-label">Stamina</div>
              <div class="survival-value ${staminaClass}">${player.stamina}%</div>
            </div>
          </div>
          
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-name">STR</span>
              <span class="stat-value">${player.stats.STR}</span>
            </div>
            <div class="stat-item">
              <span class="stat-name">DEX</span>
              <span class="stat-value">${player.stats.DEX}</span>
            </div>
            <div class="stat-item">
              <span class="stat-name">INT</span>
              <span class="stat-value">${player.stats.INT}</span>
            </div>
            <div class="stat-item">
              <span class="stat-name">WIS</span>
              <span class="stat-value">${player.stats.WIS}</span>
            </div>
            <div class="stat-item">
              <span class="stat-name">CON</span>
              <span class="stat-value">${player.stats.CON}</span>
            </div>
            <div class="stat-item">
              <span class="stat-name">AGI</span>
              <span class="stat-value">${player.stats.AGI}</span>
            </div>
          </div>
          
          <div style="margin-top: 8px; font-size: 10px; color: #666;">
            Gold: <span style="color: #c8a96e;">${player.gold}</span> | 
            XP: <span style="color: #888;">${player.xp}</span>
          </div>
        </div>
      `;
    },
    
    renderParty(party) {
      if (!party || party.length === 0) {
        return `
          <div class="context-section">
            <div class="context-section-title">Party</div>
            <div class="empty-party">No companions</div>
          </div>
        `;
      }
      
      const members = party.map(member => {
        const hpPct = Math.round((member.hp / member.max_hp) * 100);
        return `
          <div class="party-member">
            <div class="party-member-name">${member.name}</div>
            <div class="party-member-hp">HP: ${member.hp}/${member.max_hp}</div>
            <div class="party-member-hp-bar">
              <div class="party-member-hp-fill" style="width: ${hpPct}%"></div>
            </div>
          </div>
        `;
      }).join('');
      
      return `
        <div class="context-section">
          <div class="context-section-title">Party (${party.length})</div>
          <div class="party-list">
            ${members}
          </div>
        </div>
      `;
    },
    
    renderMap(map) {
      if (!map || !map.current) {
        return `
          <div class="context-section">
            <div class="context-section-title">Location</div>
            <div class="empty-party">Unknown location</div>
          </div>
        `;
      }
      
      const exits = Object.entries(map.exits || {}).map(([direction, exit]) => `
        <div class="map-exit">
          <span class="map-exit-direction">${direction.toUpperCase()}</span>: ${exit.name}
        </div>
      `).join('') || '<div style="color: #555; font-size: 10px;">No visible exits</div>';
      
      return `
        <div class="context-section">
          <div class="context-section-title">Location</div>
          
          <div class="map-current">
            <div class="map-current-name">${map.current.name}</div>
            <div class="map-current-zone">${map.current.zone || 'Wilderness'}</div>
          </div>
          
          <div class="map-exits">
            ${exits}
          </div>
        </div>
      `;
    },
    
    renderInventory(inventory) {
      if (!inventory) {
        return `
          <div class="context-section">
            <div class="context-section-title">Inventory</div>
            <div class="empty-party">Empty</div>
          </div>
        `;
      }
      
      const items = (inventory.items || []).map(item => `
        <div class="inventory-item">
          <span>${item.name}</span>
          <span class="inventory-item-type">${item.type}</span>
        </div>
      `).join('') || '<div style="color: #555; font-size: 10px;">No items</div>';
      
      const moreIndicator = inventory.has_more ? 
        '<div class="inventory-more">... more items</div>' : '';
      
      return `
        <div class="context-section">
          <div class="context-section-title">Inventory</div>
          
          <div class="inventory-count">
            ${inventory.count || 0} items
            ${inventory.equipment ? `| Equipped: ${Object.keys(inventory.equipment).length}` : ''}
          </div>
          
          <div class="inventory-list">
            ${items}
            ${moreIndicator}
          </div>
        </div>
      `;
    },
    
    renderEnvironment(environment) {
      if (!environment) {
        return `
          <div class="context-section">
            <div class="context-section-title">Environment</div>
            <div class="empty-party">Unknown</div>
          </div>
        `;
      }
      
      // Weather icons
      const weatherIcons = {
        'sunny': '☀',
        'cloudy': '☁',
        'rainy': '🌧',
        'windy': '💨',
        'stormy': '⛈'
      };
      
      // Visibility icons
      const visibilityIcons = {
        'Bright': '☀',
        'Dim': '⛅',
        'Dark': '🌑',
        'Pitch Black': '⚫'
      };
      
      const weatherIcon = weatherIcons[environment.weather] || '☁';
      const visibilityIcon = visibilityIcons[environment.visibility] || '◐';
      
      return `
        <div class="context-section">
          <div class="context-section-title">Environment</div>
          
          <div class="environment-row">
            <span class="environment-icon">🕐</span>
            <span class="environment-label">Time</span>
            <span class="environment-value">${environment.time_string || '--:--'}</span>
          </div>
          <div class="environment-detail">${environment.time_of_day || 'Unknown'}</div>
          
          <div class="environment-row">
            <span class="environment-icon">${weatherIcon}</span>
            <span class="environment-label">Weather</span>
            <span class="environment-value">${environment.weather || 'Unknown'}</span>
          </div>
          
          <div class="environment-row">
            <span class="environment-icon">🌡</span>
            <span class="environment-label">Temp</span>
            <span class="environment-value">${environment.temperature || 'Unknown'}</span>
          </div>
          
          <div class="environment-row">
            <span class="environment-icon">${visibilityIcon}</span>
            <span class="environment-label">Light</span>
            <span class="environment-value">${environment.visibility || 'Unknown'}</span>
          </div>
        </div>
      `;
    }
  };
  
  // Expose to global scope
  window.ContextPanel = ContextPanel;
})();
