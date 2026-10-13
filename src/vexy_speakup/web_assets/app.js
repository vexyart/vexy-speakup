// this_file: src/vexy_speakup/web_assets/app.js
import {installFolders, installSettings} from './dialogs.js';
export const $ = id => document.getElementById(id);
export async function api(path, body) {
  const response = await fetch('/api/' + path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail));
  return result;
}
let localError='';
export function fail(error) { localError=error.message; $('error').textContent = localError; }
export function action(id, callback) { $(id).onclick = async () => { try { localError=''; $('error').textContent=''; await callback(); await refresh(); } catch(error) { fail(error); } }; }
let chainInfo={}, manifest=null, manifestKey='', globalChoices={}, speakerChoices={}, busy=false;
function audio(path) {
  const player=document.createElement('audio'); player.controls=true; player.preload='metadata'; player.src=path;
  player.addEventListener('play',()=>document.querySelectorAll('audio').forEach(other=>{if(other!==player)other.pause();}));
  return player;
}
function showGroup() {
  if(!manifest)return;
  const index=Number($('group').value), group=manifest.groups[index];
  $('original').pause(); $('original').src=`/api/audio/${index}/-1`;
  $('clip-detail').textContent=`${group.start.toFixed(1)}–${(group.start+group.duration).toFixed(1)} seconds${group.overlap?' · overlapping voices':''}`;
  $('chains').replaceChildren();
  const names=[...new Set(group.variants.map(row=>row.chain))];
  names.forEach(name=>{
    const card=document.createElement('div'); card.className='chain';
    const title=document.createElement('h3'); title.textContent=name+(chainInfo[name]?.open_source?' · fully open source':''); card.append(title);
    const tones=document.createElement('div'); tones.className='tones';
    group.variants.forEach((row,variant)=>{
      if(row.chain!==name)return;
      const tone=document.createElement('div'); tone.className='tone';
      const label=document.createElement('label'), choice=document.createElement('input');
      choice.type='radio'; choice.name=manifest.speaker_mode?'speaker-choice':`chain-${name}`;
      const selected=manifest.speaker_mode?speakerChoices[group.id]:{chain:name,brightness:globalChoices[name]};
      choice.checked=selected?.chain===name&&selected?.brightness===row.brightness;
      choice.disabled=Boolean(row.error)||!row.output||busy;
      choice.dataset.unavailable=String(Boolean(row.error)||!row.output);
      choice.onchange=()=>{
        if(manifest.speaker_mode)speakerChoices[group.id]={chain:name,brightness:row.brightness};
        else globalChoices[name]=row.brightness;
        updateCount();
      };
      label.append(choice,document.createTextNode(' '+(row.brightness===0?'Preset tone':row.brightness>0?'Brighter +3 dB':'Less bright −3 dB')));
      tone.append(label);
      if(row.output)tone.append(audio(`/api/audio/${index}/${variant}`));
      if(row.error){const error=document.createElement('p');error.className='failed';error.textContent=row.error;tone.append(error);}
      tones.append(tone);
    });
    card.append(tones);
    if(!manifest.speaker_mode){const clear=document.createElement('button');clear.textContent='Skip this chain';clear.onclick=()=>{delete globalChoices[name];showGroup();};card.append(clear);}
    $('chains').append(card);
  });
  updateCount();
}
function updateCount(){
  $('choice-detail').textContent=manifest.speaker_mode?`${Object.keys(speakerChoices).length} of ${manifest.groups.length} speakers chosen`:`${Object.keys(globalChoices).length} chain outputs selected; choices apply to every recording.`;
}
async function refresh(){
  const state=await api('state'); busy=state.busy;
  $('status').textContent=state.message; $('error').textContent=state.error||localError;
  $('cancel').hidden=!busy;
  ['prepare','save','run','load-job','load-preview','settings','folder','speaker','backend','final-master','annotations','workers'].forEach(id=>$(id).disabled=busy);
  $('run').disabled=busy||!state.job_path;
  if(state.job_path)$('job-path').value=state.job_path;
  if(state.manifest&&state.manifest.manifest_path!==manifestKey){
    manifest=state.manifest;manifestKey=manifest.manifest_path;globalChoices={};speakerChoices={};
    $('folder').value=state.input_dir;
    $('listening').hidden=false;$('speaker').checked=manifest.speaker_mode;
    $('speaker-options').hidden=!manifest.speaker_mode;
    $('master-choice').hidden=!manifest.speaker_mode;
    const masters=manifest.masters||(manifest.master_name?[manifest.master_name]:[]);
    $('final-master').replaceChildren(new Option('None · loudness and peak only',''),...masters.map(name=>new Option(`${name} master`,name)));
    $('group').replaceChildren(...manifest.groups.map((group,index)=>new Option(`${group.label}${group.speaker?' · speaker '+group.speaker:''}`,index)));
    showGroup();
  } else if(!state.manifest&&manifest){manifest=null;manifestKey='';$('listening').hidden=true;}
  document.querySelectorAll('#chains input').forEach(input=>input.disabled=busy||input.dataset.unavailable==='true');
  if(state.job_path){
    const job=await api('job');$('job-summary').replaceChildren();
    const summary=document.createElement('p');summary.textContent=`${job.status} · ${job.tasks.filter(task=>task.status==='complete').length}/${job.tasks.length} outputs · ${job.output_directory}`;$('job-summary').append(summary);
    job.tasks.forEach(task=>{const item=document.createElement('div');item.className='task';item.textContent=`${task.status} · ${task.output.split('/').pop()}${task.error?' · '+task.error:''}`;$('job-summary').append(item);});
  }
}
$('group').onchange=showGroup;
$('original').addEventListener('play',()=>document.querySelectorAll('#chains audio').forEach(player=>player.pause()));
$('speaker').onchange=()=>{$('speaker-options').hidden=!$('speaker').checked;};
function selectedChains(){
  const names=[...document.querySelectorAll('#chains-available input:checked')].map(input=>input.value);
  if(!names.length)throw new Error('Choose at least one chain to compare');
  return names;
}
function showChainOptions(rows){
  chainInfo=Object.fromEntries(rows.map(row=>[row.name,row]));
  $('chains-available').replaceChildren(...rows.map(row=>{
    const label=document.createElement('label'), box=document.createElement('input');
    box.type='checkbox'; box.value=row.name; box.checked=row.suggested; box.disabled=!row.available;
    label.title=row.available?'':'Needs '+row.missing.join(', ');
    label.append(box,document.createTextNode(' '+row.name+(row.open_source?' · open source':'')+(row.available?'':' · unavailable')));
    return label;
  }));
}
action('prepare',()=>api('preview',{input_dir:$('folder').value,speaker_mode:$('speaker').checked,diarizer:$('backend').value,diarization_dir:$('annotations').value,workers:Number($('workers').value),chains:selectedChains()}));
action('save',()=>api('schedule',{global_choices:globalChoices,speaker_choices:speakerChoices,output_dir:$('output').value,master_name:manifest?.speaker_mode?$('final-master').value:''}));
action('run',()=>api('run',{workers:Number($('workers').value),force:$('force').checked}));
action('cancel',()=>api('cancel',{}));
action('load-job',()=>api('job/load',{path:$('job-path').value}));
action('load-preview',()=>api('preview/load',{path:$('manifest-path').value}));
installFolders();installSettings();
document.addEventListener('settings-saved',()=>api('chains').then(showChainOptions).catch(fail));
async function init(){
  const [state,settings,chains]=await Promise.all([api('state'),api('settings'),api('chains')]);
  $('folder').value=state.input_dir;$('workers').value=settings.values.processing.workers;
  showChainOptions(chains);
  await refresh(); setInterval(()=>refresh().catch(fail),1000);
}
init().catch(fail);
