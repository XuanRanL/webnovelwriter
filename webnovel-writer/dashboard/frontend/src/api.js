/**
 * API 请求工具函数
 */

const BASE = '';  // 开发时由 vite proxy 代理到 FastAPI

export async function fetchJSON(path, params = {}) {
    const url = new URL(path, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });
    const res = await fetch(url.toString());
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
}

/**
 * 订阅 SSE 实时事件流
 * @param {function} onMessage  收到 data 时回调
 * @returns {function} 取消订阅函数
 */
export function subscribeSSE(onMessage) {
    const es = new EventSource(`${BASE}/api/events`);
    es.onmessage = (e) => {
        try {
            onMessage(JSON.parse(e.data));
        } catch { /* ignore parse errors */ }
    };
    es.onerror = () => {
        // 自动重连由 EventSource 处理
    };
    return () => es.close();
}
