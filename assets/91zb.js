// 基于 iPlayer 2.0.5 版本
async function iPlayerMain(number, index, page) {
    try {
        console.log("App版本号:", iPlayer.appVersion());
        iUI.showHUD('wait', '加载中...');
        
        let payload = await getEncryptedRoomList(0);
        console.log(JSON.stringify(payload));
        iUI.clearAllHUD();
        iUI.reloadData(payload);
                        
    } catch(err) {
        iUI.clearAllHUD();
        iUI.showHUD('error', err.message);
        console.log("运行时错误:", err.stack || err);
    }
}

async function getEncryptedRoomList(pageIndex) {
    let options = {
        url: `https://api.199189.xyz/91zb/api?iplayer`
    };
    
    return await IPNetwork.request(options, (backendResponse, isEncrypted) => {
        
        if (isEncrypted) {
            return backendResponse;
        }
        
        let sourceList = backendResponse?.result?.items || [];
        // 1. 映射列表元素
        let formattedList = sourceList.map(item => {
            return {
                address: item.video_url || "",
                name: item.title || "未知房间",
                image: item.cover_pic || "",
                roomId: String(item.id || ""),
                hot: String(item.viewers || "0"),
                plat: "91直播"
            };
        });
        
        // 2. 组装根节点
        return {
            title: "91直播",
            page: pageIndex,
            pageSize: 20,
            mutableDuty: true,
            data: formattedList // 组装好的播放数组
        };
    });
}

/**
 * IPNetwork - 智能双驱网络中间件
 * 支持明文直接清洗，支持密文穿透并下发解析图纸
 */
class IPNetwork {
    static async request(options, adapter) {
        return new Promise((resolve, reject) => {
            iNetwork.get(options, function(err, res, body) {
                if (err !== null) {
                    return reject(new Error(`网络请求失败: ${err}`));
                }

                let rawData = {};
                try {
                    rawData = (typeof body === 'string' && body.trim() !== '') ? JSON.parse(body) : body;
                } catch (e) {
                    return reject(new Error('接口返回非标准 JSON'));
                }

                const isEncrypted = (typeof rawData.sign === 'string' && typeof rawData.data === 'string');

                try {
                    const bridgePayload = adapter(rawData, isEncrypted);
                    
                    if (!bridgePayload || typeof bridgePayload !== 'object') {
                        throw new Error('Adapter 必须返回一个字典对象');
                    }

                    if (isEncrypted) {
                        if (!bridgePayload.sign || !bridgePayload.data) {
                            throw new Error('密文模式下，原样返回 sign 和 data 字段');
                        }
                    } else {
                        if (!Array.isArray(bridgePayload.data)) {
                            bridgePayload.data = [];
                        }
                    }
                    
                    resolve(bridgePayload);
                } catch (adapterError) {
                    reject(new Error(`数据适配层崩溃: ${adapterError.message}`));
                }
            });
        });
    }
}
