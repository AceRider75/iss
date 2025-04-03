// app.js
const mapSwitcher = {
  currentMap: 'map1',
  init: function() {
    document.querySelectorAll('.map-selector').forEach(btn => {
      btn.addEventListener('click', (e) => {
        this.currentMap = e.target.dataset.map;
        this.loadMapBackground(`maps/${this.currentMap}.png`);
        this.loadCSVData(`data/${this.currentMap}.csv`);
      });
    });
  },
  loadMapBackground: (src) => {
    document.getElementById('main-map').style.backgroundImage = 
      `url(${src}), var(--grid-gradient)`;
  }
};
