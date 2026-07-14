import { api, ApiError, CopingCreateInput, CopingPatchInput, EventInput } from './api';
const keyPrefix='kurilka-event-queue:';
const maxQueuedEvents=100;
const key=(userId:string)=>`${keyPrefix}${userId}`;
const read=(userId:string):EventInput[]=>{try{return JSON.parse(localStorage.getItem(key(userId))||'[]')}catch{return []}};
export function enqueue(userId:string|null,event:EventInput){if(!userId)return; localStorage.setItem(key(userId),JSON.stringify([...read(userId),event].slice(-maxQueuedEvents)));}
const syncInFlight=new Map<string,Promise<void>>();
async function syncQueuedOnce(userId:string){
  if(!userId||!navigator.onLine)return;
  const queued=read(userId);
  for(let index=0;index<queued.length;index+=1){
    try{await api.event(queued[index])}
    catch(error){
      if(error instanceof ApiError&&error.status===401){localStorage.removeItem(key(userId));return}
      localStorage.setItem(key(userId),JSON.stringify(queued.slice(index)));
      return;
    }
  }
  localStorage.setItem(key(userId),'[]');
  await syncCopingQueued(userId);
}
export function syncQueued(userId:string|null):Promise<void>{
  if(!userId)return Promise.resolve();
  const existing=syncInFlight.get(userId);
  if(existing)return existing;
  const pending=syncQueuedOnce(userId).finally(()=>{if(syncInFlight.get(userId)===pending)syncInFlight.delete(userId);});
  syncInFlight.set(userId,pending);
  return pending;
}

type QueuedCoping = { create: CopingCreateInput; patches: CopingPatchInput[] };
const copingKey=(userId:string)=>`kurilka-coping-queue:${userId}`;
const readCoping=(userId:string):QueuedCoping[]=>{try{return JSON.parse(localStorage.getItem(copingKey(userId))||'[]')}catch{return []}};
export function enqueueCopingStart(userId:string|null,create:CopingCreateInput){if(!userId)return; const queue=readCoping(userId); if(!queue.some(item=>item.create.client_session_id===create.client_session_id))queue.push({create,patches:[]}); localStorage.setItem(copingKey(userId),JSON.stringify(queue.slice(-20)));}
export function enqueueCopingPatch(userId:string|null,clientSessionId:string,patch:CopingPatchInput){if(!userId)return; const queue=readCoping(userId); const item=queue.find(entry=>entry.create.client_session_id===clientSessionId); if(item)item.patches.push(patch); localStorage.setItem(copingKey(userId),JSON.stringify(queue));}
export async function syncCopingQueued(userId:string|null){
  if(!userId||!navigator.onLine)return;
  const queued=readCoping(userId);
  for(let index=0;index<queued.length;index+=1){
    const item=queued[index];
    try{const session=await api.startCoping(item.create);for(const patch of item.patches)await api.updateCoping(session.id,patch)}
    catch(error){
      if(error instanceof ApiError&&error.status===401){localStorage.removeItem(copingKey(userId));return}
      localStorage.setItem(copingKey(userId),JSON.stringify(queued.slice(index)));
      return;
    }
  }
  localStorage.setItem(copingKey(userId),'[]');
}
export function clearQueued(userId:string|null){if(userId){localStorage.removeItem(key(userId));localStorage.removeItem(copingKey(userId));}}
