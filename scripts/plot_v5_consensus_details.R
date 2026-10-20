#!/usr/bin/env Rscript
library(jsonlite)
library(ggplot2)
folder <- 'v5/results/dev_check_1_consensus_details'
d <- fromJSON(file.path(folder,'plot_data.json'))
labels <- c('rejection','denial','nonexistence','excluded','uncoded')
names <- c('Rejection','Denial','Nonexistence','Excluded','Uncoded')
d$consensus <- factor(d$consensus,levels=rev(labels),labels=rev(names))
d$model_label <- factor(d$model_label,levels=labels,labels=names)
d$language <- factor(d$language,levels=c('English','German','Hebrew','Spanish','Tagalog'))
d$model <- factor(d$model,levels=c('Gemma','Qwen'))
d$annotation <- ifelse(is.na(d$pct_of_consensus),paste0(d$n,'\nNA'),sprintf('%d\n%.1f%%',d$n,100*d$pct_of_consensus))
p <- ggplot(d,aes(x=model_label,y=consensus,fill=pct_of_consensus))+
 geom_tile(color='white',linewidth=.8)+geom_text(aes(label=annotation),size=3.5,lineheight=1.05)+
 facet_grid(language~model)+
 scale_fill_gradient(low='white',high='#67a9cf',limits=c(0,1),na.value='#eeeeee',labels=function(x)paste0(x*100,'%'))+
 coord_fixed()+labs(title='Model output versus human consensus',subtitle='Cells: count and percentage within each human-consensus row. Diagonal cells are agreement.',
 x='Model output',y='Human consensus',fill='Within row',
 caption='Dev check 1; human-union repetition exclusion. Consensus requires identical human labels after collapsing Nonpossession.\nExcluded and Uncoded retained; gray rows have no consensus examples. No adjudicated gold standard.')+
 theme_minimal(base_size=12)+theme(panel.grid=element_blank(),strip.text=element_text(face='bold'),
 axis.text.x=element_text(angle=30,hjust=1),legend.position='bottom',legend.key.width=grid::unit(1.2,'cm'),plot.caption=element_text(hjust=0),
 plot.title=element_text(face='bold'),panel.spacing=grid::unit(1,'lines'))
ggsave(file.path(folder,'confusion_matrices.png'),p,width=12,height=17.5,dpi=160,bg='white')
ggsave(file.path(folder,'confusion_matrices.pdf'),p,width=12,height=17.5,device='pdf')
# Independently reconstruct every cell and denominator directly from the row audit.
report <- fromJSON(file.path(folder,'report.json'),simplifyVector=FALSE)
checks <- 0L
for(lang in names(report$languages)){
 x <- report$languages[[lang]]; rows <- x$audit
 stopifnot(length(rows)==x$n)
 truth <- vapply(rows,function(r)r$label,character(1))
 stopifnot(all(vapply(rows,function(r)r$label==r$other_label,logical(1))))
 ids <- vapply(rows,function(r)r$record_id,character(1));stopifnot(!anyDuplicated(ids))
 for(model in c('gemma','qwen')){
  predictions <- vapply(rows,function(r)r[[model]],character(1));m <- x$models[[model]]
  stopifnot(sum(truth==predictions)==m$agree_n,abs(mean(truth==predictions)-m$agreement)<1e-12)
  for(cell in m$cells){
   n <- sum(truth==cell$consensus & predictions==cell$model_label)
   nr <- sum(truth==cell$consensus);nc <- sum(predictions==cell$model_label)
   stopifnot(n==cell$n,nr==cell$consensus_n,nc==cell$predicted_n)
   if(nr)stopifnot(abs(n/nr-cell$pct_of_consensus)<1e-12) else stopifnot(is.null(cell$pct_of_consensus))
   if(nc)stopifnot(abs(n/nc-cell$pct_of_prediction)<1e-12) else stopifnot(is.null(cell$pct_of_prediction))
   checks <- checks+1L
  }
 }
}
cat('Verified',checks,'confusion cells and directional percentages independently against audit rows in R.\n')
