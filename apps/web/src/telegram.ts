type TelegramWebApp = {initData:string;ready:()=>void;expand:()=>void;themeParams?:Record<string,string>;BackButton?:{show:()=>void;hide:()=>void};openLink?:(url:string)=>void};
declare global { interface Window { Telegram?: { WebApp?: TelegramWebApp } } }
export function telegram() { return window.Telegram?.WebApp; }
export function initialiseTelegram() { const app=telegram(); app?.ready(); app?.expand(); const theme=app?.themeParams; if(theme?.bg_color) document.documentElement.style.setProperty('--tg-bg',theme.bg_color); if(theme?.text_color) document.documentElement.style.setProperty('--tg-text',theme.text_color); return app; }
