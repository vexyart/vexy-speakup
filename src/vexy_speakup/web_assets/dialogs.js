// this_file: src/vexy_speakup/web_assets/dialogs.js
import {$,api,action,fail} from './app.js';
export function installFolders(){
  let field=null,current='';
  async function browse(path){
    const result=await api('folders?path='+encodeURIComponent(path));current=result.path;
    $('browse-path').value=current;$('browse-up').onclick=()=>browse(result.parent).catch(fail);
    $('folders').replaceChildren(...result.folders.map(name=>{
      const button=document.createElement('button');button.textContent=name+'/';button.onclick=()=>browse(current+'/'+name).catch(fail);return button;
    }));
  }
  document.querySelectorAll('[data-browse]').forEach(button=>button.onclick=async()=>{
    field=$(button.dataset.browse);
    try{await browse(field.value||$('folder').value);$('browser').showModal();}catch(error){fail(error);}
  });
  $('browse-go').onclick=()=>browse($('browse-path').value).catch(fail);
  $('browse-select').onclick=()=>{field.value=current;$('browser').close();};
  $('browse-close').onclick=()=>$('browser').close();
}
export function installSettings(){
  action('settings',async()=>{
    const result=await api('settings');
    for(const [key,id] of [['plugin_root','plugin-root']]){
      $(id).value=result.overrides[key]||result.values.paths[key];$(id).disabled=Boolean(result.overrides[key]);
    }
    $('settings-info').textContent=result.path+(Object.values(result.overrides).some(Boolean)?' · Paths set by environment variables override saved values.':'');
    $('settings-dialog').showModal();
  });
  action('settings-save',async()=>{await api('settings',{plugin_root:$('plugin-root').value,workers:Number($('workers').value)});$('settings-dialog').close();document.dispatchEvent(new Event('settings-saved'));});
  $('settings-close').onclick=()=>$('settings-dialog').close();
}
