// Apply the saved theme before styles paint. Storage may be disabled by the browser.
(()=>{let theme='dark';try{const saved=localStorage.getItem('carla-theme');if(saved==='light'||saved==='dark')theme=saved}catch{}document.documentElement.dataset.theme=theme})();
