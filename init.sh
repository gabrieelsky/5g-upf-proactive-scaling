#sudo sysctl -p
#sudo apt-mark hold kubeadm kubelet kubectl
sudo swapoff -a
sudo kubeadm reset -f --cri-socket unix:///var/run/cri-dockerd.sock
sudo rm -rf /etc/cni/net.d
sudo kubeadm init --apiserver-advertise-address=$(ip -4 addr show ens3 | grep -oP '(?<=inet\s)\d+(\.\d+){3}') --cri-socket unix:///var/run/cri-dockerd.sock --pod-network-cidr=10.244.0.0/16
sleep 2
sudo mkdir -p $HOME/.kube
sleep 1
sudo \cp /etc/kubernetes/admin.conf $HOME/.kube/config
sleep 1
sudo chown $(id -u):$(id -g) $HOME/.kube/config
sleep 2
kubectl taint nodes $(hostname | tr '[:upper:]' '[:lower:]') node-role.kubernetes.io/control-plane:NoSchedule-
sleep 10
kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml
sleep 10
git clone https://github.com/k8snetworkplumbingwg/multus-cni.git
sleep 5
cd multus-cni
kubectl apply -f https://raw.githubusercontent.com/k8snetworkplumbingwg/multus-cni/master/deployments/multus-daemonset.yml
cd ..
