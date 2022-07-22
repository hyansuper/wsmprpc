class RPCClientError extends Error{
    constructor(message) {
        super(message);
        this.name = 'RPCClientError';
    }
}
class RPCServerError extends Error{
    constructor(message) {
        super(message);
        this.name = 'RPCServerError';
    }
}

class RPCStream {
    static _stream_end = Object();
    constructor(size) {
        this.size = size;
        this._closed = false;
        this._resolve = null;
        this._reject = null;
        this._q = [];
    }

    get closed() {
        return this._closed;
    }

    get full() {
        return this.size>0 && this.size<=this._q.length;
    }

    put_nowait(v, force=false) {
        if(!this._closed) {
            if(this.full && !force) return;
            if(this._resolve) {
                this._resolve(v);
                this._resolve = null;
            } else {
                this._q.push(v);
            }
        }
    }

    get() {
        return new Promise((resolve, reject)=>{
            this._q.length?resolve(this._q.shift()):this._resolve=resolve;
        });
    }

    [Symbol.asyncIterator]() {
        return this;
    }

    force_close_nowait() {
        this.put_nowait(RPCStream._stream_end, true);
        this._close = true;
    }

    next() {
        return this.get().then(v=>{            
            if(v instanceof Error) throw v;            
            return (v===RPCStream._stream_end)?{done:true}:{done:false, value:v};
        })
    }
}

class RPCFuture extends Promise {
    constructor(cb, cancel_fn, response_stream) {
        super(cb);
        this._cancel_fn = cancel_fn;
        this._cancelled = false;
        this._response_stream = response_stream;
        this._rj = null;
    }

    get resolve() {
        return this._rj.resolve;
    }

    get reject() {
        return this._rj.reject;
    }

    get cancelled() {
        return this._cancelled;
    }

    get response_stream() {
        if(!this._response_stream)
            throw new RPCClientError('Not a response-streaming rpc');
        return this._response_stream;
    }

    cancel() {
        if(!this._cancelled){
            this._cancel_fn();
            this._cancelled = true;
        }
    }

    [Symbol.asyncIterator]() {
        if (!this._response_stream)
            throw new RPCClientError('Not a response-streaming rpc');
        if (this._cancelled)
            throw new RPCClientError('Cancelled');
        return this._response_stream;
    }
}

const RPCMsgType = {
    NOTIFY: 1,
    REQUEST: 2,
    RESPONSE: 3,
    REQUEST_STREAM_CHUNCK: 4,
    RESPONSE_STREAM_CHUNCK: 5,
    REQUEST_STREAM_END: 6,
    RESPONSE_STREAM_END: 7,
    REQUEST_CANCEL: 8,
    RESPONSE_CANCEL: 9,
}

const RPCMethodType = {
    STR: 1,
    NUM: 2,
    STR_NUM: 3,
}

class RPCClient{    

    constructor(ws, meth_num_first=false) {
        this._ws = ws;        
        this._mid = 1;
        this._meth_num_first = meth_num_first;
        this._tasks = {};
        this._init_fut = new Promise(r=>{this._rpc_info_resolve=r});
    }

    async _on_data (data) {
        try{
            const msg = msgpack.deserialize(await data.data.arrayBuffer());
            if (!this._rpc_info){
                [this._rpc_meth_type, this._rpc_info] = msg;
                this._rpc_ls = this._rpc_info.map(([sig])=> sig.substring(0, sig.indexOf('(')));
                this._use_meth_num = this._rpc_meth_type == RPCMethodType.NUM ||
                                        this._meth_num_first && this._rpc_meth_type == RPCMethodType.STR_NUM;
                this._rpc_info_resolve();
                return;
            }
            const [msgtype, msgid] = msg.slice(0, 2);
            const p = this._tasks[msgid.toString()];
            if (p)
                switch(msgtype) {
                    case RPCMsgType.RESPONSE:
                        const [err, result] = msg.slice(2);
                        if(err){
                            if(!p.cancelled) {
                                const e = new RPCServerError(err);
                                p.reject(e);
                                p._response_stream && p._response_stream.put_nowait(e, true);
                            }
                        }else{
                            p.resolve(result);
                        }
                        this._pop_promise(msgid);
                        break;

                    case RPCMsgType.RESPONSE_STREAM_CHUNCK:
                        p.response_stream.put_nowait(msg[2], true);
                        break;

                    case RPCMsgType.RESPONSE_STREAM_END:
                        p.response_stream.force_close_nowait();
                        p.resolve();
                        this._pop_promise(msgid);
                        break;                        
                }
         } catch (e) {
            console.error(e);
         }            
    }

    async connect(ws) {
        if (this._ws && ws) throw 'Socket is already set';
        if (!this._ws) this._ws = ws;
        this._ws.onmessage = this._on_data.bind(this);
        await this._init_fut;
    }

    get rpc_info() {
        return this._rpc_info;
    }

    rpc(method, params, options={}) {
        const index = this._rpc_ls.indexOf(method);
        if(index < 0) throw new RPCClientError("Unknown RPC method "+method);
        var [req, resp] = this._rpc_info[index].slice(2, 4);
        var request_stream = options.request_stream;
        if (req && !request_stream)
            throw new RPCClientError(method+' must take "request_stream" as the a keyword arg.')
        else if (!req && request_stream)
            throw new RPCClientError(method+' is not a request-streaming RPC.')
        var response_stream = resp?(options.response_stream || new RPCStream(options.q_size||0)):null;
        const msgid = this._next_msgid();
        const rj={};
        const p = new RPCFuture((resolve, reject)=>{
            rj.resolve=resolve;
            rj.reject=reject;
            this._send_request(msgid, this._use_meth_num?this._rpc_ls.indexOf(method):method, params);
            if (request_stream){
                if(typeof request_stream[Symbol.iterator] === 'function'){
                    for(var e of request_stream)
                        this._send_stream_chunck(msgid, e)
                    this._send_stream_end(msgid)
                }else if(typeof request_stream[Symbol.asyncIterator] === 'function'){
                    (async function(){
                        for await(var e of request_stream)
                            this._send_stream_chunck(msgid, e)
                        this._send_stream_end(msgid)
                    }).bind(this)();
                }
            }
        }, this._cancel.bind(this, msgid), response_stream);
        p._rj = rj;
        this._tasks[msgid] = p;
        return p;
    }

    _cancel(msgid) {
        const p = this._pop_promise(msgid);
        if(p) {
            const e = new RPCClientError('Cancelled');
            p.reject(e);
            p._response_stream && p._response_stream.put_nowait(e, true);
        }
        this._send_cancel(msgid);
    }

    _send_cancel(msgid) {
        this._ws.send(msgpack.serialize([RPCMsgType.REQUEST_CANCEL, msgid]));
    }

    _send_stream_chunck(msgid, chunck) {
        this._ws.send(msgpack.serialize([RPCMsgType.REQUEST_STREAM_CHUNCK, msgid, chunck]));
    }

    _send_stream_end(msgid) {
        this._ws.send(msgpack.serialize([RPCMsgType.REQUEST_STREAM_END, msgid]));
    }

    _send_request(msgid, method, params) {
        this._ws.send(msgpack.serialize([RPCMsgType.REQUEST, msgid, method, params]));
    }

    _pop_promise(msgid) {
        const p = this._tasks[msgid.toString()];
        delete this._tasks[msgid.toString()];
        return p;
    }

    _next_msgid() {
        if(this._mid > 2**20)
            this._mid = 1;
        this._mid += 1;
        return this._mid;
    }


    static async connect (ws) {
        var client = new RPCClient();
        await client.connect(ws);
        return client;
    }
}