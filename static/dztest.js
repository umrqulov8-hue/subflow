document.addEventListener('DOMContentLoaded',function(){
  var dz=document.getElementById('uploadArea');
  var fi=document.getElementById('fileInput');

  if(!dz||!fi){
    alert('ERROR: uploadArea='+dz+' fileInput='+fi);
    return;
  }

  dz.addEventListener('click',function(e){
    e.preventDefault();
    e.stopPropagation();
    fi.click();
  });

  fi.addEventListener('change',function(){
    if(this.files.length){
      var names=[];
      for(var i=0;i<this.files.length;i++)names.push(this.files[i].name);
      alert('Selected: '+names.join(', '));
      this.value='';
    }
  });
});
